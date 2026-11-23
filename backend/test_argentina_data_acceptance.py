"""Suite de pruebas de aceptación para la integración complementaria de Argentina Data MCP.

Cubre exhaustivamente las 8 pruebas especificadas en la Sección 11 del requerimiento:
1. El RAG local alcanza el umbral -> cero llamadas a la API externa.
2. El RAG local no alcanza el umbral y la API encuentra artículos relevantes -> respuesta fundamentada en InfoLEG.
3. El RAG local no alcanza el umbral y la API devuelve resultados irrelevantes -> respuesta de desconocimiento.
4. La API devuelve disponible: false -> evalúa versión 'original'; si no hay contenido, responde desconocimiento.
5. La API Key no está configurada -> funciona normalmente con base local y desconocimiento sin error.
6. La API devuelve 401, 402, 429 o 500 -> manejo controlado de errores sin excepciones no capturadas.
7. Se recupera texto original con modificaciones registradas -> incluye aviso de vigencia y no lo presenta como vigente categórico.
8. Pregunta sin relación con legislación argentina -> desconocimiento sin forzar resultados jurídicos.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Permitir importaciones directas de app
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.argentina_data import (
    ArgentinaDataClient,
    ArgentinaDataLegalResult,
    RetrievedArticle,
    argentina_data_client,
    _is_relevant_legal_result,
)
from app.config import settings
from app.rag_pipeline import rag_pipeline
from app.prompts import OUT_OF_DOMAIN_RESPONSE


def test_1_local_rag_hits_threshold_zero_api_calls():
    """Prueba 1: El RAG local alcanza el umbral -> no se llama a Argentina Data MCP."""
    print("\n--- Ejecutando Prueba 1: RAG local alcanza umbral ---")
    query = "¿Qué dice la ley sobre el secreto profesional y la protección de fuentes?"

    with patch.object(argentina_data_client, "query_legal_fallback") as mock_fallback:
        res = rag_pipeline.query(query)
        assert res.is_grounded is True, "Debería estar fundamentada"
        assert res.response_type == "grounded"
        assert len(res.sources) > 0, "Debe tener fuentes locales"
        # La API externa NO debe haber sido invocada
        assert mock_fallback.call_count == 0, f"Se llamó a la API externa {mock_fallback.call_count} veces cuando no debía"
        print("  ✓ Prueba 1 superada: 0 llamadas a Argentina Data MCP cuando el RAG local alcanza el umbral.")


def test_2_local_fails_api_finds_relevant_norm():
    """Prueba 2: El RAG local no alcanza el umbral y la API encuentra artículos relevantes."""
    print("\n--- Ejecutando Prueba 2: RAG local no alcanza umbral y API encuentra Ley 26.032 ---")
    query = "¿Qué establece la legislación argentina sobre la libertad de expresión en Internet?"

    sample_search_results = [
        {
            "id_norma": 107145,
            "numero": "26032",
            "tipo": "Ley",
            "titulo": "SERVICIO DE INTERNET - GARANTIA CONSTITUCIONAL - LIBERTAD DE EXPRESION",
            "norma_ref": "infoleg:107145",
            "estado_vigencia": "modificada",
            "url": "https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=107145",
        }
    ]
    sample_normativa_result = {
        "disponible": True,
        "version": "original",
        "norma": {
            "norma_ref": "infoleg:107145",
            "cita": "Ley 26.032",
            "titulo": "SERVICIO DE INTERNET - GARANTIA CONSTITUCIONAL - LIBERTAD DE EXPRESION",
            "estado_vigencia": "modificada",
        },
        "resultados_por_unidad": [
            {
                "unidad": "art 1",
                "estado": "ok",
                "texto": "ARTICULO 1° — La búsqueda, recepción y difusión de información e ideas de toda índole, a través del servicio de Internet, se considera comprendido dentro de la garantía constitucional que ampara la libertad de expresión.",
            },
            {
                "unidad": "art 2",
                "estado": "ok",
                "texto": "ARTICULO 2° — La presente ley comenzará a regir a partir del día siguiente al de su publicación en el Boletín Oficial.",
            },
        ],
        "url": "https://servicios.infoleg.gob.ar/infolegInternet/anexos/105000-109999/107145/norma.htm",
        "aviso_vigencia": "Este es el texto original y puede no reflejar 1 modificación registrada; la última es Decreto 512/2009",
    }

    # Limpiamos caché para que evalúe la llamada
    from app.argentina_data import _LEGAL_QUERY_CACHE
    _LEGAL_QUERY_CACHE.clear()

    # Simulamos que la base local no supera el umbral (p. ej. score 0.35 < 0.45)
    with patch.object(rag_pipeline, "retrieve_with_threshold", return_value=([], 0.35, 0.45)):
        with patch.object(argentina_data_client, "search_infoleg", return_value=sample_search_results):
            with patch.object(argentina_data_client, "fetch_normativa", return_value=sample_normativa_result):
                res = rag_pipeline.query(query)
                assert res.is_grounded is True, "Debería fundamentarse con InfoLEG"
                assert res.response_type == "grounded"
                assert len(res.sources) > 0, "Debe contener citas de InfoLEG"
                assert any("26.032" in s.document_title or "26032" in s.source_file for s in res.sources), f"Debe citar Ley 26.032: {[s.document_title for s in res.sources]}"
                assert "infoleg" in res.sources[0].source_file.lower() or "infoleg" in res.sources[0].category.lower()
                assert "Identificación del Dilema" in res.answer
                assert "Marco Normativo" in res.answer
                assert "Análisis de la Situación" in res.answer
                assert "Conclusión o Recomendación" in res.answer
                assert "http" in res.answer, "Debe incluir enlace oficial"
                print("  ✓ Prueba 2 superada: Respuesta fundamentada con artículos y enlace oficial de InfoLEG.")


def test_3_local_fails_and_api_irrelevant():
    """Prueba 3: El RAG local no alcanza el umbral y la API devuelve resultados irrelevantes."""
    print("\n--- Ejecutando Prueba 3: API devuelve resultados irrelevantes ---")
    # Caso: falsos positivos (como edulcorantes artificiales al buscar inteligencia artificial)
    fake_item = {
        "id_norma": 99999,
        "numero": "11111",
        "tipo": "Ley",
        "titulo": "REGIMEN DE EDULCORANTES ARTIFICIALES Y SACARINA",
        "organismo": "MINISTERIO DE SALUD",
    }
    is_rel = _is_relevant_legal_result(fake_item, ["inteligencia", "artificial"])
    assert is_rel is False, "El filtro debe descartar edulcorantes como falso positivo de IA"

    # Verificamos que cuando el RAG local no supera el umbral y la API devuelve irrelevante (None), se mantiene OUT_OF_DOMAIN_RESPONSE
    with patch.object(rag_pipeline, "retrieve_with_threshold", return_value=([], 0.25, 0.45)):
        with patch.object(argentina_data_client, "query_legal_fallback", return_value=None):
            res = rag_pipeline.query("¿Qué normativa aplica a los edulcorantes artificiales?")
            assert res.is_grounded is False
            assert res.response_type == "no_info"
            assert res.answer == OUT_OF_DOMAIN_RESPONSE
    print("  ✓ Prueba 3 superada: Filtra falsos positivos y mantiene la respuesta de desconocimiento.")


def test_4_api_disponible_false():
    """Prueba 4: La API devuelve disponible: false incluso tras evaluar original."""
    print("\n--- Ejecutando Prueba 4: disponible: false ---")
    client = ArgentinaDataClient()
    with patch.object(client, "fetch_normativa", return_value={"disponible": False, "nota": "No digitalizada"}):
        with patch.object(client, "search_infoleg", return_value=[{"id_norma": 123, "numero": "999", "titulo": "COMUNICACION DIGITAL", "tipo": "Ley"}]):
            res = client.query_legal_fallback("alguna consulta sobre comunicacion digital de prueba")
            assert res is None, "Debe retornar None cuando disponible es false en ambas versiones"

    with patch.object(rag_pipeline, "retrieve_with_threshold", return_value=([], 0.25, 0.45)):
        with patch.object(argentina_data_client, "query_legal_fallback", return_value=None):
            chat_res = rag_pipeline.query("consulta sin texto disponible en infoleg")
            assert chat_res.is_grounded is False
            assert chat_res.response_type == "no_info"
            assert chat_res.answer == OUT_OF_DOMAIN_RESPONSE
    print("  ✓ Prueba 4 superada: Trata disponible: false de forma segura y devuelve respuesta de desconocimiento.")


def test_5_api_key_not_configured():
    """Prueba 5: La API Key no está configurada -> funciona localmente y no rompe."""
    print("\n--- Ejecutando Prueba 5: API Key no configurada ---")
    client_unconfigured = ArgentinaDataClient(api_key=None)
    with patch.object(settings, "argentina_data_api_key", None):
        assert client_unconfigured.is_configured() is False
        assert client_unconfigured.search_infoleg("test") == []
        assert client_unconfigured.fetch_normativa("infoleg:123") is None
        assert client_unconfigured.query_legal_fallback("libertad de expresion") is None

    # El chatbot local sigue funcionando con sus PDFs
    res = rag_pipeline.query("¿Qué dice la ley sobre el secreto profesional y la protección de fuentes?")
    assert res.is_grounded is True
    print("  ✓ Prueba 5 superada: Sin API key la base local funciona y el fallback devuelve None sin excepciones.")


def test_6_api_http_errors_handled():
    """Prueba 6: La API devuelve 401, 402, 429 o 500."""
    print("\n--- Ejecutando Prueba 6: Manejo de errores HTTP 401, 402, 429 y 500 ---")
    import httpx

    for status in (401, 402, 429, 500):
        mock_resp = MagicMock()
        mock_resp.status_code = status
        with patch("httpx.Client.get", return_value=mock_resp):
            client = ArgentinaDataClient(api_key="test_key")
            results = client.search_infoleg("test")
            assert results == [], f"Debe retornar lista vacía ante HTTP {status}"
            normativa = client.fetch_normativa("infoleg:107145")
            assert normativa is None, f"Debe retornar None ante HTTP {status}"

    print("  ✓ Prueba 6 superada: Errores 401, 402, 429 y 500 manejados limpiamente sin romper.")


def test_7_original_version_disclaimer():
    """Prueba 7: Se recupera texto original con modificaciones registradas -> advertencia clara."""
    print("\n--- Ejecutando Prueba 7: Texto original y advertencia de vigencia ---")
    mock_result = ArgentinaDataLegalResult(
        id_norma=107145,
        numero="26032",
        tipo="Ley",
        titulo="SERVICIO DE INTERNET - LIBERTAD DE EXPRESION",
        cita="Ley 26.032",
        norma_ref="infoleg:107145",
        estado_vigencia="modificada",
        version="original",
        url="https://servicios.infoleg.gob.ar/infolegInternet/anexos/105000-109999/107145/norma.htm",
        aviso_vigencia="Este es el texto original y puede no reflejar 1 modificación registrada; la última es Decreto 512/2009",
        articulos=[
            RetrievedArticle(unidad="art 1", texto="La búsqueda y difusión de información a través de Internet comprende la garantía constitucional de libertad de expresión.")
        ],
    )

    with patch.object(rag_pipeline, "retrieve_with_threshold", return_value=([], 0.25, 0.45)):
        with patch.object(argentina_data_client, "query_legal_fallback", return_value=mock_result):
            res = rag_pipeline.query("¿Qué garantiza la ley de internet?")
            assert res.is_grounded is True
            assert "original" in res.answer.lower(), "Debe advertir que es versión original"
            assert "modificaci" in res.answer.lower(), "Debe advertir sobre modificaciones registradas"
            assert "https://servicios.infoleg.gob.ar" in res.answer, "Debe incluir enlace oficial"
    print("  ✓ Prueba 7 superada: No presenta texto original como vigente categórico e incluye aviso de modificaciones.")


def test_8_out_of_domain_no_legal_forcing():
    """Prueba 8: Pregunta sin relación con legislación argentina -> no forzar respuesta."""
    print("\n--- Ejecutando Prueba 8: Pregunta sin relación con legislación ---")
    res = rag_pipeline.query("¿Cómo se prepara una tarta de manzana casera?")
    assert res.is_grounded is False
    assert res.response_type == "no_info"
    assert res.answer == OUT_OF_DOMAIN_RESPONSE
    print("  ✓ Prueba 8 superada: Mantiene respuesta de desconocimiento sin forzar leyes irrelevantes.")


def run_all():
    print("======================================================================")
    print("Iniciando Suite de Pruebas de Aceptación — Argentina Data MCP en ÁgoraIA")
    print("======================================================================")
    test_1_local_rag_hits_threshold_zero_api_calls()
    test_2_local_fails_api_finds_relevant_norm()
    test_3_local_fails_and_api_irrelevant()
    test_4_api_disponible_false()
    test_5_api_key_not_configured()
    test_6_api_http_errors_handled()
    test_7_original_version_disclaimer()
    test_8_out_of_domain_no_legal_forcing()
    print("======================================================================")
    print("¡TODAS LAS 8 PRUEBAS DE ACEPTACIÓN SE SUPERARON SATISFACTORIAMENTE!")
    print("======================================================================")


if __name__ == "__main__":
    run_all()
