"""Esquemas Pydantic de entrada y salida para la API REST de ÁgoraIA."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    """Referencia trazable a un fragmento recuperado desde ChromaDB."""

    source_file: str = Field(..., description="Nombre del archivo PDF fuente.")
    document_title: str = Field(..., description="Título oficial de la norma o informe.")
    category: str = Field(..., description="Categoría normativa o temática.")
    page: Optional[int] = Field(None, description="Número de página (base 1).")
    article_hint: Optional[str] = Field(
        None, description="Artículo, principio o hallazgo detectado en el fragmento."
    )
    relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Similitud semántica normalizada."
    )
    excerpt: str = Field(..., description="Extracto textual recuperado para el análisis.")


class StructuredAnalysis(BaseModel):
    """Desglose obligatorio de 4 puntos definido en la Parte 1."""

    identificacion_dilema: str = Field(
        default="",
        description="1. Resumen breve de los principios éticos o normativos en tensión.",
    )
    marco_normativo: str = Field(
        default="",
        description="2. Explicación de las leyes, estatutos o guías ADEPA con cita explícita.",
    )
    analisis_situacion: str = Field(
        default="",
        description="3. Evaluación crítica de los posibles caminos y sus consecuencias éticas.",
    )
    conclusion_recomendacion: str = Field(
        default="",
        description="4. Síntesis reflexiva y buena práctica recomendada.",
    )


class ChatTurn(BaseModel):
    """Un turno previo de la conversación."""

    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=6000)


class CaseInfo(BaseModel):
    """Caso o dilema del corpus, usable como consulta de ejemplo o caso relacionado."""

    id: str
    title: str
    category: str
    summary: str
    prompt: str


class ChatRequest(BaseModel):
    """Solicitud de consulta o análisis de dilema ético para ÁgoraIA."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=4000,
        description="Consulta conceptual o caso dilemático a analizar.",
    )
    history: List[ChatTurn] = Field(
        default_factory=list,
        max_length=20,
        description="Turnos previos para mantener el hilo de la conversación.",
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=15,
        description="Cantidad máxima de fragmentos a recuperar (opcional).",
    )
    score_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Umbral mínimo de similitud para evitar alucinaciones (opcional).",
    )


class ChatResponse(BaseModel):
    """Respuesta completa y trazable devuelta por ÁgoraIA."""

    bot_name: str = Field(default="ÁgoraIA")
    question: str
    answer: str
    is_grounded: bool = Field(
        ...,
        description="True si la respuesta supera el umbral y se apoya en fuentes; False si se activó el corte Cero Alucinaciones.",
    )
    max_relevance_score: float = Field(
        default=0.0,
        description="Mayor puntaje de similitud obtenido en la búsqueda semántica.",
    )
    threshold_used: float = Field(
        ..., description="Umbral de relevancia aplicado en esta consulta."
    )
    structured_sections: Optional[StructuredAnalysis] = Field(
        default=None,
        description="Secciones parseadas cuando la respuesta sigue la estructura de 4 puntos.",
    )
    sources: List[SourceCitation] = Field(default_factory=list)
    response_type: Literal["grounded", "no_info", "smalltalk", "blocked"] = Field(
        default="grounded",
        description="Tipo de respuesta: fundamentada, sin información, saludo o bloqueada por seguridad.",
    )
    retrieval_query: Optional[str] = Field(
        default=None,
        description="Consulta usada para la búsqueda cuando se contextualizó con el historial.",
    )
    related_cases: List[CaseInfo] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    """Valoración del usuario sobre una respuesta."""

    question: str = Field(..., max_length=4000)
    answer: str = Field(..., max_length=20000)
    rating: Literal["up", "down"]
    comment: Optional[str] = Field(default=None, max_length=1000)
    response_type: str = "grounded"
    max_relevance_score: float = 0.0


class IngestRequest(BaseModel):
    """Parámetros para disparar la ingesta documental hacia ChromaDB."""

    reset: bool = Field(
        default=False,
        description="Si es True, reinicia la colección vectorial antes de indexar.",
    )


class IngestResponse(BaseModel):
    """Resultado de la ingesta de PDFs hacia ChromaDB."""

    status: str
    files_processed: int
    pages_loaded: int
    chunks_indexed: int
    collection_name: str
    persist_directory: str


class KnowledgeSourceInfo(BaseModel):
    """Información pública de un documento disponible en el corpus de ÁgoraIA."""

    filename: str
    title: str
    category: str
    short_citation: str
    description: str
    exists_on_disk: bool
    file_size_bytes: int = 0


class SourcesListResponse(BaseModel):
    """Listado de fuentes normativas configuradas y estado del índice vectorial."""

    bot_name: str = "ÁgoraIA"
    total_documents: int
    indexed_chunks: int
    sources: List[KnowledgeSourceInfo]


class HealthResponse(BaseModel):
    """Estado de salud del backend RAG de ÁgoraIA."""

    status: str
    bot_name: str
    version: str
    llm_provider: str
    embedding_provider: str
    score_threshold: float
    indexed_chunks: int
    pdfs_available: int
