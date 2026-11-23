"""Módulo complementario para consultar legislación argentina mediante Argentina Data MCP (InfoLEG).

Este módulo actúa EXCLUSIVAMENTE como fuente de respaldo secundaria cuando la recuperación
local en los PDFs de ÁgoraIA no alcanza el umbral de similitud semántica.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger("agora_ia.argentina_data")

# Caché en memoria para evitar llamadas redundantes dentro del ciclo de vida del backend
_LEGAL_QUERY_CACHE: Dict[str, Optional["ArgentinaDataLegalResult"]] = {}

# Palabras vacías en español para extracción de términos
STOPWORDS = {
    "a", "al", "algo", "algun", "alguna", "ante", "bajo", "cabe", "con", "contra",
    "de", "del", "desde", "donde", "durante", "el", "ella", "ellas", "ellos", "en",
    "entre", "era", "es", "esa", "esas", "ese", "esos", "esta", "estas", "este",
    "estos", "ha", "habia", "hace", "hacia", "hasta", "la", "las", "le", "les",
    "lo", "los", "mas", "me", "mi", "mis", "muy", "no", "nos", "o", "para", "pero",
    "por", "que", "quien", "quienes", "se", "segun", "si", "sin", "so", "sobre",
    "su", "sus", "te", "tiene", "tienen", "tras", "tu", "un", "una", "unas", "unos",
    "y", "ya", "yo", "establece", "dice", "sobre", "respecto", "como", "cual", "cuales",
    "argentina", "argentino", "argentinos", "legislacion", "ley", "leyes", "norma", "normas"
}

# Términos relevantes del dominio comunicacional, tecnológico, periodístico y legal
DOMAIN_POSITIVE_KEYWORDS = {
    "internet", "expresion", "prensa", "periodis", "comunicacion", "informacion",
    "datos", "habeas", "privacidad", "autor", "intelectual", "secreto", "fuente",
    "audiovisual", "digital", "tecnologia", "inteligencia", "red", "difusion",
    "noticia", "medio", "publica", "publico", "plataforma", "software", "computa",
    "telecomunicac", "archivo", "censura", "discriminac", "imagen", "voz"
}

# Términos que alertan sobre falsos positivos (como edulcorantes artificiales)
FALSE_POSITIVE_NEGATIVE_KEYWORDS = {
    "edulcorante", "alimento", "azucar", "sacarina", "ciclamato", "fertilizante",
    "ganadero", "fauna", "pesca", "mineria", "semillas", "agroquimico"
}

# Catálogo asistido de temas frecuentes fuera de los 8 PDFs para mapeo rápido y preciso
KNOWN_TOPIC_MAPPINGS: List[Dict[str, Any]] = [
    {
        "patterns": [r"libertad\s+de\s+expresi[óo]n\s+(?:en\s+)?internet", r"internet.*libertad\s+de\s+expresi[óo]n", r"ley\s+26\.?032"],
        "query": "libertad de expresion internet",
        "tipo": "ley",
        "expected_numero": "26032",
        "default_units": "art 1,art 2",
    },
    {
        "patterns": [r"argentina\s+digital", r"neutralidad\s+de\s+red", r"ley\s+27\.?078"],
        "query": "argentina digital neutralidad red",
        "tipo": "ley",
        "expected_numero": "27078",
        "default_units": "art 1,art 56,art 57",
    },
    {
        "patterns": [r"acceso\s+a\s+la\s+informaci[óo]n\s+p[úu]blica", r"ley\s+27\.?275"],
        "query": "acceso a la informacion publica",
        "tipo": "ley",
        "expected_numero": "27275",
        "default_units": "art 1,art 2,art 4",
    },
    {
        "patterns": [r"firma\s+digital", r"documento\s+electr[óo]nico", r"ley\s+25\.?506"],
        "query": "firma digital",
        "tipo": "ley",
        "expected_numero": "25506",
        "default_units": "art 1,art 2,art 3",
    },
    {
        "patterns": [r"delitos?\s+inform[áa]ticos?", r"cibercrimen", r"ley\s+26\.?388"],
        "query": "delitos informaticos",
        "tipo": "ley",
        "expected_numero": "26388",
        "default_units": "art 1,art 2",
    },
]


@dataclass
class RetrievedArticle:
    """Artículo legal recuperado desde Normativa (InfoLEG)."""

    unidad: str
    texto: str
    caracteres: Optional[int] = None


@dataclass
class ArgentinaDataLegalResult:
    """Resultado estructurado de consulta jurídica a Argentina Data MCP."""

    id_norma: int
    numero: str
    tipo: str
    titulo: str
    cita: str
    norma_ref: str
    estado_vigencia: str
    version: str
    url: str
    aviso_vigencia: Optional[str] = None
    articulos: List[RetrievedArticle] = field(default_factory=list)


def _has_valid_api_key() -> bool:
    """Verifica si la clave de Argentina Data está presente y no es un marcador de ejemplo."""
    key = (settings.argentina_data_api_key or "").strip()
    return bool(key) and not key.startswith("reemplazar") and not key.startswith("tu-clave")


def _extract_article_units_from_question(question: str) -> Optional[str]:
    """Detecta si la consulta del usuario pide artículos específicos (ej. 'artículo 1', 'art 5')."""
    matches = re.findall(r"\bart[íi]culo\s+(\d+[a-z]?)\b|\bart\.?\s*(\d+[a-z]?)\b", question, re.IGNORECASE)
    if not matches:
        return None
    numbers = []
    for m in matches:
        num = m[0] or m[1]
        if num and num not in numbers:
            numbers.append(f"art {num}")
    return ",".join(numbers[:5]) if numbers else None


def _is_relevant_legal_result(item: Dict[str, Any], query_terms: List[str]) -> bool:
    """
    Comprueba que el resultado devuelto por InfoLEG sea pertinente al dominio y a la pregunta.
    Evita falsos positivos como 'edulcorantes artificiales' al buscar 'inteligencia artificial'.
    """
    titulo = str(item.get("titulo", "")).lower()
    organismo = str(item.get("organismo", "")).lower()
    full_text = f"{titulo} {organismo}"

    # Descartar si contiene palabras de falsos positivos no jurídicos
    for neg in FALSE_POSITIVE_NEGATIVE_KEYWORDS:
        if neg in full_text:
            return False

    # Verificar presencia de términos de dominio
    domain_match = any(pos in full_text for pos in DOMAIN_POSITIVE_KEYWORDS)
    if not domain_match:
        return False

    # Si hubo búsqueda relajada o se especificaron términos de consulta, verificar al menos 1 coincidencia
    if query_terms:
        matches = [term for term in query_terms if term in full_text]
        if not matches:
            return False

    return True


class ArgentinaDataClient:
    """Cliente HTTP modular y robusto para consumir la API REST de Argentina Data MCP."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.api_key = api_key or settings.argentina_data_api_key
        self.base_url = (base_url or settings.argentina_data_base_url).rstrip("/")
        self.timeout = timeout or settings.argentina_data_timeout_seconds

    def is_configured(self) -> bool:
        """Indica si el cliente cuenta con las credenciales requeridas."""
        return _has_valid_api_key()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "AgoraIA-RAG-Bot/1.0",
        }

    def search_infoleg(
        self,
        query: str,
        tipo: Optional[str] = "ley",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Consulta Endpoint 1: /legislacion/infoleg
        Busca leyes o decretos relacionados con el término consultado.
        """
        if not self.is_configured():
            return []

        url = f"{self.base_url}/legislacion/infoleg"
        params: Dict[str, Any] = {"query": query, "limit": limit}
        if tipo:
            params["tipo"] = tipo

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers(), params=params)

                if resp.status_code == 401:
                    logger.warning("Argentina Data MCP: Error 401 (No autenticado). Verifique ARGENTINA_DATA_API_KEY.")
                    return []
                if resp.status_code == 402:
                    logger.warning("Argentina Data MCP: Error 402 (Cupo agotado).")
                    return []
                if resp.status_code == 429:
                    logger.warning("Argentina Data MCP: Error 429 (Límite de velocidad alcanzado).")
                    return []
                if resp.status_code >= 500:
                    logger.warning("Argentina Data MCP: Error %s en el servidor remoto.", resp.status_code)
                    return []

                resp.raise_for_status()
                data = resp.json()
                resultados = data.get("resultados", [])
                return resultados if isinstance(resultados, list) else []

        except httpx.TimeoutException:
            logger.warning("Argentina Data MCP: Timeout al buscar en /legislacion/infoleg.")
            return []
        except Exception as exc:
            logger.warning("Argentina Data MCP: Excepción en search_infoleg: %s", exc)
            return []

    def fetch_normativa(
        self,
        norma_ref: str,
        unidades: str = "art 1,art 2",
        version: str = "actualizado",
    ) -> Optional[Dict[str, Any]]:
        """
        Consulta Endpoint 2: /legislacion/normativa
        Recupera artículos específicos de una norma.
        """
        if not self.is_configured():
            return None

        url = f"{self.base_url}/legislacion/normativa"
        params = {
            "norma": norma_ref,
            "unidades": unidades,
            "version": version,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers(), params=params)

                if resp.status_code in (401, 402, 429) or resp.status_code >= 500:
                    logger.warning("Argentina Data MCP: Error %s al recuperar normativa %s.", resp.status_code, norma_ref)
                    return None

                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict):
                    return data
                return None

        except httpx.TimeoutException:
            logger.warning("Argentina Data MCP: Timeout al consultar /legislacion/normativa para %s.", norma_ref)
            return None
        except Exception as exc:
            logger.warning("Argentina Data MCP: Excepción en fetch_normativa: %s", exc)
            return None

    def query_legal_fallback(self, question: str) -> Optional[ArgentinaDataLegalResult]:
        """
        Flujo completo de consulta complementaria:
        1. Identifica términos o patrones temáticos.
        2. Busca normas en InfoLEG (/legislacion/infoleg).
        3. Filtra resultados relevantes y descarta falsos positivos.
        4. Recupera artículos mediante /legislacion/normativa (intentando 'actualizado', y luego 'original' si corresponde).
        5. Valida que exista contenido disponible y suficiente.
        """
        if not self.is_configured():
            return None

        # Caché rápida en memoria
        normalized_q = question.strip().lower()
        if normalized_q in _LEGAL_QUERY_CACHE:
            return _LEGAL_QUERY_CACHE[normalized_q]

        # 1. Estrategia de búsqueda: mapeo asistido o extracción de términos
        matched_mapping: Optional[Dict[str, Any]] = None
        for mapping in KNOWN_TOPIC_MAPPINGS:
            if any(re.search(pat, normalized_q, re.IGNORECASE) for pat in mapping["patterns"]):
                matched_mapping = mapping
                break

        query_terms: List[str] = []
        if matched_mapping:
            search_query = matched_mapping["query"]
            tipo_filter = matched_mapping.get("tipo", "ley")
            target_units = _extract_article_units_from_question(question) or matched_mapping.get("default_units", "art 1,art 2")
            expected_num = matched_mapping.get("expected_numero")
        else:
            # Extracción limpia de términos significativos
            words = [re.sub(r"[^\w]", "", w) for w in normalized_q.split()]
            query_terms = [w for w in words if len(w) >= 4 and w not in STOPWORDS]
            if not query_terms:
                _LEGAL_QUERY_CACHE[normalized_q] = None
                return None
            search_query = " ".join(query_terms[:4])
            tipo_filter = "ley"
            target_units = _extract_article_units_from_question(question) or "art 1,art 2"
            expected_num = None

        # 2. Paso A: Buscar legislación en InfoLEG
        candidate_items = self.search_infoleg(query=search_query, tipo=tipo_filter, limit=5)
        if not candidate_items:
            # Intento secundario sin filtro de tipo
            candidate_items = self.search_infoleg(query=search_query, tipo=None, limit=5)

        if not candidate_items:
            _LEGAL_QUERY_CACHE[normalized_q] = None
            return None

        # 3. Filtrar y seleccionar la norma más pertinente
        selected_item: Optional[Dict[str, Any]] = None
        if expected_num:
            for item in candidate_items:
                if str(item.get("numero", "")).strip() == expected_num:
                    selected_item = item
                    break

        if not selected_item:
            for item in candidate_items:
                if _is_relevant_legal_result(item, query_terms):
                    selected_item = item
                    break

        if not selected_item:
            _LEGAL_QUERY_CACHE[normalized_q] = None
            return None

        norma_ref = selected_item.get("norma_ref") or f"infoleg:{selected_item.get('id_norma')}"
        id_norma = selected_item.get("id_norma", 0)
        numero = str(selected_item.get("numero", ""))
        tipo = str(selected_item.get("tipo", "Norma"))
        titulo = str(selected_item.get("titulo", "")).strip()
        official_url = str(selected_item.get("url", f"https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id={id_norma}"))

        # 4. Paso B y C: Recuperar artículos (intentando 'actualizado' y luego 'original')
        normativa_data = self.fetch_normativa(norma_ref=norma_ref, unidades=target_units, version="actualizado")
        version_used = "actualizado"

        # Si no está disponible en 'actualizado', intentar 'original' según el diseño
        if not normativa_data or not normativa_data.get("disponible", False):
            nota = (normativa_data or {}).get("nota", "") if isinstance(normativa_data, dict) else ""
            if "original" in nota.lower() or not normativa_data or not normativa_data.get("disponible"):
                normativa_data_orig = self.fetch_normativa(norma_ref=norma_ref, unidades=target_units, version="original")
                if normativa_data_orig and normativa_data_orig.get("disponible", False):
                    normativa_data = normativa_data_orig
                    version_used = "original"

        if not normativa_data or not normativa_data.get("disponible", False):
            _LEGAL_QUERY_CACHE[normalized_q] = None
            return None

        # 5. Extraer artículos y validar suficiencia de contenido
        raw_articulos = normativa_data.get("resultados_por_unidad", [])
        if not isinstance(raw_articulos, list) or not raw_articulos:
            _LEGAL_QUERY_CACHE[normalized_q] = None
            return None

        recovered_articles: List[RetrievedArticle] = []
        for art in raw_articulos:
            if art.get("estado") == "ok" and art.get("texto", "").strip():
                clean_text = " ".join(art["texto"].split())
                recovered_articles.append(
                    RetrievedArticle(
                        unidad=str(art.get("unidad", "")).strip(),
                        texto=clean_text,
                        caracteres=art.get("caracteres_totales"),
                    )
                )

        if not recovered_articles:
            _LEGAL_QUERY_CACHE[normalized_q] = None
            return None

        # Datos complementarios de la norma recuperada
        norma_meta = normativa_data.get("norma", {}) if isinstance(normativa_data.get("norma"), dict) else {}
        cita = norma_meta.get("cita") or f"{tipo} {numero}".strip()
        norma_titulo = norma_meta.get("titulo") or titulo
        estado_vigencia = norma_meta.get("estado_vigencia") or selected_item.get("estado_vigencia", "no_especificado")
        aviso_vigencia = normativa_data.get("aviso_vigencia")
        final_url = normativa_data.get("url") or official_url

        result = ArgentinaDataLegalResult(
            id_norma=id_norma,
            numero=numero,
            tipo=tipo,
            titulo=norma_titulo,
            cita=cita,
            norma_ref=norma_ref,
            estado_vigencia=estado_vigencia,
            version=version_used,
            url=final_url,
            aviso_vigencia=aviso_vigencia,
            articulos=recovered_articles,
        )

        _LEGAL_QUERY_CACHE[normalized_q] = result
        return result


# Instancia única del cliente
argentina_data_client = ArgentinaDataClient()
