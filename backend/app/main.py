"""API REST de FastAPI para ÁgoraIA (Ética Periodística, Comunicación Digital e IA)."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.cases import list_cases
from app.config import DOCUMENT_CATALOG, settings
from app.ingestion import KnowledgeBaseIngestor
from app.prompts import CHATBOT_NAME
from app.rag_pipeline import rag_pipeline
from app.schemas import (
    CaseInfo,
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    KnowledgeSourceInfo,
    SourcesListResponse,
)
from app.security import RateLimiter

logger = logging.getLogger("agora_ia")
rate_limiter = RateLimiter(max_requests=30, window_seconds=60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Indexa automáticamente los 8 PDFs si la base vectorial inicia vacía."""
    if rag_pipeline.get_indexed_chunks_count() == 0:
        try:
            ingestor = KnowledgeBaseIngestor()
            result = ingestor.ingest_all(reset=False)
            rag_pipeline.reload_vectorstore()
            logger.info("Ingesta automática inicial completada: %s", result)
        except Exception as exc:
            logger.warning("No se pudo ejecutar la ingesta inicial automática: %s", exc)
    yield


app = FastAPI(
    title=f"{CHATBOT_NAME} — API RAG de Ética Periodística e IA",
    description=(
        "Backend especializado en ética periodística, derecho a la información en Argentina "
        "y gobernanza de IA generativa en medios de comunicación."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse, tags=["Sistema"])
def health_check() -> HealthResponse:
    """Verifica el estado operativo del servicio RAG y su colección vectorial."""
    pdf_dir = settings.pdf_dir_path
    pdfs_available = len(list(pdf_dir.glob("*.pdf"))) if pdf_dir.exists() else 0

    return HealthResponse(
        status="ok",
        bot_name=CHATBOT_NAME,
        version=settings.app_version,
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
        score_threshold=settings.similarity_score_threshold,
        indexed_chunks=rag_pipeline.get_indexed_chunks_count(),
        pdfs_available=pdfs_available,
    )


@app.get("/api/sources", response_model=SourcesListResponse, tags=["Base de Conocimiento"])
def list_knowledge_sources() -> SourcesListResponse:
    """Lista los documentos normativos que conforman la base de conocimiento de ÁgoraIA."""
    pdf_dir = settings.pdf_dir_path
    items = []

    for filename, entry in DOCUMENT_CATALOG.items():
        file_path = pdf_dir / filename
        exists = file_path.exists()
        size = file_path.stat().st_size if exists else 0
        items.append(
            KnowledgeSourceInfo(
                filename=entry.filename,
                title=entry.title,
                category=entry.category,
                short_citation=entry.short_citation,
                description=entry.description,
                exists_on_disk=exists,
                file_size_bytes=size,
            )
        )

    # Incluir PDFs adicionales si el usuario agrega nuevos archivos al directorio
    if pdf_dir.exists():
        for extra_pdf in sorted(pdf_dir.glob("*.pdf")):
            if extra_pdf.name not in DOCUMENT_CATALOG:
                items.append(
                    KnowledgeSourceInfo(
                        filename=extra_pdf.name,
                        title=extra_pdf.stem.replace("_", " ").title(),
                        category="Documentación Complementaria",
                        short_citation=extra_pdf.name,
                        description="Documento PDF adicional agregado al corpus local.",
                        exists_on_disk=True,
                        file_size_bytes=extra_pdf.stat().st_size,
                    )
                )

    return SourcesListResponse(
        bot_name=CHATBOT_NAME,
        total_documents=len(items),
        indexed_chunks=rag_pipeline.get_indexed_chunks_count(),
        sources=items,
    )


@app.post("/api/ingest", response_model=IngestResponse, tags=["Base de Conocimiento"])
def ingest_knowledge_base(payload: IngestRequest = IngestRequest()) -> IngestResponse:
    """Ejecuta la lectura con PyPDFLoader, fragmentación legal e indexación vectorial."""
    try:
        ingestor = KnowledgeBaseIngestor()
        result = ingestor.ingest_all(reset=payload.reset)
        rag_pipeline.reload_vectorstore()
        return IngestResponse(**result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error durante la ingesta documental: {exc}"
        ) from exc


@app.get("/api/cases", response_model=List[CaseInfo], tags=["Base de Conocimiento"])
def list_case_catalog() -> List[CaseInfo]:
    """Catálogo de casos y dilemas del corpus para explorar."""
    return list_cases()


@app.post("/api/feedback", tags=["Evaluación"])
def submit_feedback(payload: FeedbackRequest) -> dict:
    """Registra la valoración (👍/👎) de una respuesta para evaluación posterior."""
    feedback_file = settings.chroma_dir_path.parent / "feedback.jsonl"
    feedback_file.parent.mkdir(parents=True, exist_ok=True)
    record = payload.model_dump()
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    with feedback_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"status": "saved"}


@app.post("/api/chat", response_model=ChatResponse, tags=["Chatbot RAG"])
def chat_with_agora(payload: ChatRequest, request: Request) -> ChatResponse:
    """Procesa una consulta o dilema ético aplicando umbral anti-alucinaciones."""
    client_id = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client_id):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas consultas en poco tiempo. Espera un momento e inténtalo de nuevo.",
        )
    try:
        return rag_pipeline.query(
            question=payload.question,
            top_k=payload.top_k,
            score_threshold=payload.score_threshold,
            history=payload.history,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error en /api/chat")
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar la consulta en {CHATBOT_NAME}. Inténtalo nuevamente.",
        ) from exc
