"""Catálogo de casos y dilemas del corpus de ÁgoraIA.

Cada caso apunta a los documentos del corpus donde se fundamenta, para poder
recuperarlo como "caso relacionado" y ofrecerlo como consulta de ejemplo.
"""

from typing import Dict, List

from app.schemas import CaseInfo


CASES: List[Dict] = [
    {
        "id": "perfil-openai",
        "title": "Demanda de Perfil contra OpenAI y Microsoft",
        "category": "Derechos de autor e IA",
        "summary": "Editorial Perfil demanda a OpenAI y Microsoft por presunto uso no autorizado de contenidos periodísticos (Informe ADEPA 2026).",
        "prompt": "¿Qué plantea el caso de la demanda de Editorial Perfil contra OpenAI y Microsoft según el Informe ADEPA 2026?",
        "source_files": ["11_IA_y-medios-argentinos-2026.pdf"],
    },
    {
        "id": "bloquear-vs-encontrado",
        "title": "Bloquear el scraping vs. ser encontrado",
        "category": "Sostenibilidad del ecosistema informativo",
        "summary": "Dilema entre bloquear a los buscadores generativos con robots.txt o mantener visibilidad y tráfico.",
        "prompt": "¿Cuál es el dilema entre bloquear el scraping con robots.txt y ser encontrado por los buscadores según ADEPA 2026?",
        "source_files": ["11_IA_y-medios-argentinos-2026.pdf"],
    },
    {
        "id": "marco-comparado",
        "title": "Marco comparado: Canadá, Australia y la UE",
        "category": "Regulación internacional",
        "summary": "Respuestas regulatorias frente a plataformas e IA: Online News Act, News Bargaining Incentive y AI Act.",
        "prompt": "¿Qué marcos regulatorios de otros países menciona el Informe ADEPA 2026 sobre compensación a los medios por el uso de IA?",
        "source_files": ["11_IA_y-medios-argentinos-2026.pdf"],
    },
    {
        "id": "brecha-gobernanza",
        "title": "Brecha de gobernanza en las redacciones",
        "category": "Gobernanza de la IA",
        "summary": "Los medios dicen tener protocolos de IA, pero pocos periodistas los conocen.",
        "prompt": "¿Qué brecha de gobernanza de la IA detecta el Informe ADEPA 2026 entre medios y periodistas?",
        "source_files": ["11_IA_y-medios-argentinos-2026.pdf"],
    },
    {
        "id": "voz-clonada",
        "title": "Clonación de voz con IA sin aviso a la audiencia",
        "category": "Transparencia y uso de IA",
        "summary": "Uso de voces sintetizadas o recreaciones audiovisuales sin informarlo al público.",
        "prompt": "Un medio utiliza IA para clonar la voz de un locutor y recrear un audio sin avisar a la audiencia. ¿Qué principios éticos y normativos entran en tensión?",
        "source_files": [
            "12_guia-para-el-uso-de-la-ia-en-los-medios-argentinos.pdf",
            "Normas_argentinas_ejercicio_periodistico.pdf",
        ],
    },
    {
        "id": "fuentes-vs-justicia",
        "title": "Secreto de las fuentes frente a un requerimiento judicial",
        "category": "Privacidad y fuentes",
        "summary": "Un periodista debe decidir entre proteger su fuente y colaborar con la justicia.",
        "prompt": "Un periodista recibe una filtración con datos sensibles y la justicia le exige revelar su fuente. ¿Qué dicen la Constitución Nacional y la Ley 25.326?",
        "source_files": [
            "1_constitucion_de_la_nacion_argentina.pdf",
            "6_ley_d_eporteccion_de_datos_arg_ley25326.pdf",
        ],
    },
    {
        "id": "scraping-zero-click",
        "title": "Resúmenes generativos sin autorización ni compensación",
        "category": "Propiedad intelectual",
        "summary": "Un buscador con IA resume notas de un diario y reduce su tráfico (zero-click).",
        "prompt": "Un buscador con respuestas generativas resume notas de un diario sin autorización ni compensación. ¿Qué establecen la Ley 11.723 y ADEPA?",
        "source_files": [
            "4_ley11723.pdf",
            "11_IA_y-medios-argentinos-2026.pdf",
        ],
    },
    {
        "id": "menor-noticiero",
        "title": "Imágenes de un menor en un noticiero",
        "category": "Protección de la niñez",
        "summary": "Difusión de imágenes de un menor en un programa periodístico sin proteger su identidad.",
        "prompt": "Un noticiero transmitido a las 15:00 hs muestra imágenes de un menor involucrado en un hecho policial. ¿Qué establece la Ley 26.522?",
        "source_files": ["3_servicios-de-comunicacion-audiovisual-ley-26522.pdf"],
    },
    {
        "id": "retrato-interes-publico",
        "title": "Publicación de un retrato en hechos de interés público",
        "category": "Derechos personalísimos",
        "summary": "Cuándo puede publicarse la imagen de una persona sin su consentimiento.",
        "prompt": "¿Cuándo se puede publicar el retrato fotográfico de una persona sin su consentimiento según la Ley 11.723?",
        "source_files": ["4_ley11723.pdf"],
    },
    {
        "id": "nota-ia-sin-verificar",
        "title": "Nota escrita con IA sin verificación humana",
        "category": "Supervisión humana",
        "summary": "Publicación de contenido generado por IA sin control editorial.",
        "prompt": "Una redacción publica una nota generada con IA sin verificar los datos. ¿Qué responsabilidad le cabe al medio según la Guía ADEPA?",
        "source_files": [
            "12_guia-para-el-uso-de-la-ia-en-los-medios-argentinos.pdf",
            "11_IA_y-medios-argentinos-2026.pdf",
        ],
    },
]


def list_cases() -> List[CaseInfo]:
    """Devuelve todo el catálogo de casos."""
    return [CaseInfo(**{k: v for k, v in c.items() if k != "source_files"}) for c in CASES]


def find_related_cases(
    cited_files: List[str], question: str, limit: int = 3
) -> List[CaseInfo]:
    """Casos cuyo fundamento coincide con los documentos citados en la respuesta."""
    cited = set(cited_files)
    scored = []
    for case in CASES:
        if case["prompt"].strip() == question.strip():
            continue
        overlap = len(cited.intersection(case["source_files"]))
        if overlap:
            scored.append((overlap, case))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        CaseInfo(**{k: v for k, v in c.items() if k != "source_files"})
        for _, c in scored[:limit]
    ]
