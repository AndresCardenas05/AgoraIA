"""Motor RAG de ÁgoraIA con umbral de similitud y bloqueo Cero Alucinaciones."""

import re
from typing import Any, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

from app.argentina_data import ArgentinaDataLegalResult, argentina_data_client
from app.cases import find_related_cases
from app.config import settings
from app.ingestion import (
    LOCAL_INDEX_FILENAME,
    LocalCosineVectorStore,
    build_embeddings,
    is_chroma_available,
)
from app.prompts import (
    AGORA_RAG_PROMPT,
    BLOCKED_RESPONSE,
    CHATBOT_NAME,
    GREETING_RESPONSE,
    OUT_OF_DOMAIN_RESPONSE,
)
from app.schemas import ChatResponse, ChatTurn, SourceCitation, StructuredAnalysis
from app.security import detect_prompt_injection, is_smalltalk


SECTION_HEADERS_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:#{1,4}\s*)?(?:\*\*)?"
    r"(1\.\s*(?:\*\*)?Identificaci[óo]n del Dilema|"
    r"2\.\s*(?:\*\*)?Marco Normativo\s*/?\s*Base de Conocimiento|"
    r"3\.\s*(?:\*\*)?An[áa]lisis de la Situaci[óo]n|"
    r"4\.\s*(?:\*\*)?Conclusi[óo]n o Recomendaci[óo]n)"
    r"[:\*]*\s*",
    re.IGNORECASE,
)


def _has_real_api_key() -> bool:
    """Verifica si hay una clave LLM configurada y distinta a los marcadores de ejemplo."""
    if settings.llm_provider == "gemini":
        key = (settings.google_api_key or "").strip()
        return bool(key) and not key.startswith("reemplazar")
    key = (settings.openai_api_key or "").strip()
    return bool(key) and not key.startswith("sk-reemplazar")


def build_llm() -> BaseChatModel:
    """Instancia el modelo de lenguaje configurado (OpenAI o Gemini)."""
    if settings.llm_provider == "gemini":
        if not settings.google_api_key or settings.google_api_key.startswith("reemplazar"):
            raise ValueError(
                "GOOGLE_API_KEY es obligatorio cuando LLM_PROVIDER='gemini'."
            )
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_llm_model,
            google_api_key=settings.google_api_key,
            temperature=settings.llm_temperature,
        )

    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-reemplazar"):
        raise ValueError(
            "OPENAI_API_KEY es obligatorio cuando LLM_PROVIDER='openai'."
        )
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr

    return ChatOpenAI(
        model=settings.openai_llm_model,
        api_key=SecretStr(settings.openai_api_key),
        temperature=settings.llm_temperature,
    )


def parse_structured_sections(answer: str) -> Optional[StructuredAnalysis]:
    """Extrae las 4 secciones normativas de la respuesta en Markdown si están presentes."""
    matches = list(SECTION_HEADERS_PATTERN.finditer(answer))
    if len(matches) < 2:
        return None

    sections = {
        "1": "",
        "2": "",
        "3": "",
        "4": "",
    }
    for idx, match in enumerate(matches):
        header_text = match.group(1).strip()
        key = header_text[0]
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(answer)
        sections[key] = answer[start:end].strip()

    if not any(sections.values()):
        return None

    return StructuredAnalysis(
        identificacion_dilema=sections["1"],
        marco_normativo=sections["2"],
        analisis_situacion=sections["3"],
        conclusion_recomendacion=sections["4"],
    )


def _synthesize_grounded_offline_answer(
    question: str, docs_with_scores: List[Tuple[Document, float]]
) -> str:
    """
    Genera una respuesta extractiva estrictamente fundamentada en los 4 puntos
    cuando aún no hay una API key externa configurada, citando únicamente fragmentos verificados.
    """
    unique_sources: List[str] = []
    normative_bullets: List[str] = []

    for doc, score in docs_with_scores:
        meta = doc.metadata
        title = str(meta.get("document_title", "Fuente normativa"))
        page = meta.get("page", "?")
        article = meta.get("article_hint")
        ref = f"{title} (Pág. {page}" + (f", {article})" if article else ")")
        if title not in unique_sources:
            unique_sources.append(title)
        clean_excerpt = " ".join(doc.page_content.split())
        if len(clean_excerpt) > 360:
            clean_excerpt = clean_excerpt[:357] + "..."
        normative_bullets.append(
            f"- **{ref}** *(similitud {score:.0%})*: «{clean_excerpt}»"
        )

    sources_summary = ", ".join(unique_sources)
    normative_text = "\n".join(normative_bullets)

    return (
        "1. **Identificación del Dilema:**\n"
        f"La consulta planteada (*«{question}»*) involucra tensiones éticas y jurídicas en el ejercicio "
        "periodístico, la comunicación digital y el uso de Inteligencia Artificial, vinculados con la "
        f"aplicación concurrente de: **{sources_summary}**.\n\n"
        "2. **Marco Normativo / Base de Conocimiento:**\n"
        "A continuación se reproducen los pasajes verificados recuperados directamente desde el corpus documental de ÁgoraIA:\n\n"
        f"{normative_text}\n\n"
        "3. **Análisis de la Situación:**\n"
        "Desde una perspectiva crítica no binaria, los documentos recuperados obligan a ponderar los "
        "principios en tensión (tales como libertad de expresión e interés público frente a privacidad, "
        "datos sensibles, consentimiento, propiedad intelectual, transparencia hacia las audiencias y "
        "supervisión humana constante o *human-in-the-loop*). Ninguno de estos derechos debe analizarse "
        "de forma aislada respecto de las responsabilidades legales y éticas citadas en las fuentes anteriores.\n\n"
        "4. **Conclusión o Recomendación:**\n"
        "Se recomienda documentar la trazabilidad editorial de las fuentes, aplicar verificación y "
        "supervisión humana en todas las etapas, garantizar transparencia explícita hacia la audiencia "
        "cuando intervenga IA generativa y resguardar los derechos personalísimos y de autor según las "
        "normas citadas.\n\n"
        "> *Nota técnica:* Respuesta generada en **modo extractivo local** (sin invocar LLM externo) porque "
        "`OPENAI_API_KEY` / `GOOGLE_API_KEY` aún no fueron configuradas en `backend/.env`. Añade tu clave "
        "y reinicia el backend para obtener síntesis redactada por GPT-4o-mini o Gemini sobre estos mismos fragmentos."
    )


def _synthesize_infoleg_offline_answer(
    question: str, legal_res: ArgentinaDataLegalResult
) -> str:
    """Genera una respuesta en 4 puntos fundamentada en InfoLEG en modo offline."""
    art_bullets = []
    for art in legal_res.articulos:
        art_bullets.append(f"- **{art.unidad.upper()}**: «{art.texto}»")
    art_text = "\n".join(art_bullets)

    vigencia_warning = ""
    if legal_res.version == "original":
        vigencia_warning = (
            f"\n\n> ⚠️ **Aviso de vigencia y versión:** El texto de esta norma fue recuperado en su **versión original** "
            f"tal como fue publicada. InfoLEG indica que la norma tiene estado *'{legal_res.estado_vigencia}'* y "
            f"puede no reflejar modificaciones registradas"
            + (f" ({legal_res.aviso_vigencia})" if legal_res.aviso_vigencia else "")
            + f". No debe asumirse como versión vigente definitiva sin consultar la [Ficha Oficial en InfoLEG]({legal_res.url})."
        )
    else:
        vigencia_warning = (
            f"\n\n> ℹ️ **Fuente normativa:** Texto recuperado en versión **actualizada** desde la base oficial de InfoLEG "
            f"([Ver texto oficial]({legal_res.url}))."
        )

    return (
        "1. **Identificación del Dilema:**\n"
        f"La consulta planteada (*«{question}»*) no fue cubierta por los documentos locales prioritarios de ÁgoraIA, "
        f"pero fue identificada en la legislación argentina complementaria a través de **{legal_res.cita} ({legal_res.titulo})**.\n\n"
        "2. **Marco Normativo / Base de Conocimiento:**\n"
        f"A continuación se reproducen los artículos oficiales recuperados desde InfoLEG para **{legal_res.cita}**:\n\n"
        f"{art_text}{vigencia_warning}\n\n"
        "3. **Análisis de la Situación:**\n"
        f"Desde una perspectiva ético-jurídica, la aplicación de {legal_res.cita} vincula el ejercicio periodístico y "
        "comunicacional con las garantías constitucionales del Estado argentino. La norma recuperada debe interpretarse "
        "en equilibrio con la libertad de expresión, el derecho a la información de la sociedad, la protección de derechos "
        "personalísimos y los estándares de transparencia en entornos digitales e inteligencia artificial.\n\n"
        "4. **Conclusión o Recomendación:**\n"
        f"Se recomienda basar la práctica informativa y profesional en los principios tutelados por {legal_res.cita}, "
        "garantizando la debida diligencia editorial y la verificación de fuentes. "
        f"Para corroborar el alcance vigente de cualquier reforma o reglamentación posterior, consulte siempre el enlace oficial: "
        f"[{legal_res.cita} en InfoLEG]({legal_res.url})."
    )


class AgoraRAGPipeline:
    """Orquesta recuperación semántica, validación de umbral y generación fundamentada."""

    def __init__(self) -> None:
        self._embeddings = None
        self._vectorstore: Any = None
        self._llm: Optional[BaseChatModel] = None
        self._using_local_store: bool = False

    def _get_vectorstore(self) -> Any:
        if self._vectorstore is None:
            persist_dir = settings.chroma_dir_path
            persist_dir.mkdir(parents=True, exist_ok=True)
            local_index_file = persist_dir / LOCAL_INDEX_FILENAME

            if local_index_file.exists() or not is_chroma_available():
                self._vectorstore = LocalCosineVectorStore(persist_dir)
                self._using_local_store = True
            else:
                from langchain_chroma import Chroma  # type: ignore[import-not-found]

                if self._embeddings is None:
                    self._embeddings = build_embeddings()
                self._vectorstore = Chroma(
                    collection_name=settings.chroma_collection_name,
                    embedding_function=self._embeddings,
                    persist_directory=str(persist_dir),
                    collection_metadata={"hnsw:space": "cosine"},
                )
                self._using_local_store = False
        return self._vectorstore

    def reload_vectorstore(self) -> None:
        """Fuerza recarga de la referencia vectorial luego de una nueva ingesta."""
        self._vectorstore = None

    def get_indexed_chunks_count(self) -> int:
        """Devuelve la cantidad de chunks actualmente persistidos."""
        try:
            vs = self._get_vectorstore()
            if isinstance(vs, LocalCosineVectorStore):
                return vs.count()
            return int(vs._collection.count())
        except Exception:
            return 0

    def retrieve_with_threshold(
        self,
        query: str,
        k: Optional[int] = None,
        score_threshold: Optional[float] = None,
    ) -> Tuple[List[Tuple[Document, float]], float, float]:
        """
        Ejecuta similarity_search_with_relevance_scores y aplica el umbral estricto.

        Retorna:
          - Lista filtrada de (Document, score) con score >= threshold
          - Máximo score obtenido antes del filtrado
          - Umbral efectivo utilizado
        """
        top_k = k or settings.top_k
        threshold = (
            score_threshold
            if score_threshold is not None
            else settings.similarity_score_threshold
        )

        if self.get_indexed_chunks_count() == 0:
            return [], 0.0, threshold

        vs = self._get_vectorstore()
        raw_results = vs.similarity_search_with_relevance_scores(query, k=top_k)
        if not raw_results:
            return [], 0.0, threshold

        normalized_results: List[Tuple[Document, float]] = [
            (doc, max(0.0, min(1.0, float(score)))) for doc, score in raw_results
        ]
        max_score = max(score for _, score in normalized_results)
        filtered = [
            (doc, score) for doc, score in normalized_results if score >= threshold
        ]
        return filtered, max_score, threshold

    @staticmethod
    def _format_context(docs_with_scores: List[Tuple[Document, float]]) -> str:
        """Construye un bloque de contexto numerado y trazable para el System Prompt."""
        blocks: List[str] = []
        for idx, (doc, score) in enumerate(docs_with_scores, start=1):
            meta: dict[str, Any] = doc.metadata
            title = meta.get("document_title", "Fuente desconocida")
            source_file = meta.get("source_file", "desconocido.pdf")
            page = meta.get("page", "?")
            article = meta.get("article_hint")
            article_tag = f" | Referencia: {article}" if article else ""
            blocks.append(
                f"[FUENTE {idx}] {title} (Archivo: {source_file} | Pág. {page}{article_tag} | Relevancia: {score:.2f})\n"
                f"{doc.page_content}"
            )
        return "\n\n---\n\n".join(blocks)

    @staticmethod
    def _to_source_citations(
        docs_with_scores: List[Tuple[Document, float]],
    ) -> List[SourceCitation]:
        """Convierte los documentos recuperados en citas estructuradas para la UI."""
        citations: List[SourceCitation] = []
        for doc, score in docs_with_scores:
            meta = doc.metadata
            excerpt_text = " ".join(doc.page_content.split())
            if len(excerpt_text) > 320:
                excerpt_text = excerpt_text[:317] + "..."
            citations.append(
                SourceCitation(
                    source_file=str(meta.get("source_file", "desconocido.pdf")),
                    document_title=str(meta.get("document_title", "Fuente normativa")),
                    category=str(meta.get("category", "General")),
                    page=meta.get("page") if isinstance(meta.get("page"), int) else None,
                    article_hint=meta.get("article_hint"),
                    relevance_score=round(score, 4),
                    excerpt=excerpt_text,
                )
            )
        return citations

    @staticmethod
    def _build_followup_query(
        question: str, history: Optional[List[ChatTurn]]
    ) -> Optional[str]:
        """Contextualiza consultas de seguimiento (con anáfora explícita) con el último turno del usuario."""
        if not history:
            return None
        previous_user = [t.content for t in history if t.role == "user"]
        if not previous_user:
            return None
        has_cue = re.search(
            r"\b(eso|esto|esa|ese|esos|esas|esta|este|ello|ellos|ellas|ambas|ambos|otra|otro|"
            r"tambi[eé]n|anterior|mismo|misma|dicho|dicha|al respecto|lo anterior)\b",
            question.lower(),
        )
        if has_cue and len(question.split()) <= 20:
            return f"{previous_user[-1][:400]} {question}"
        return None

    @staticmethod
    def _history_messages(history: Optional[List[ChatTurn]]) -> List[BaseMessage]:
        messages: List[BaseMessage] = []
        for turn in (history or [])[-6:]:
            content = turn.content[:1500]
            messages.append(
                HumanMessage(content=content)
                if turn.role == "user"
                else AIMessage(content=content)
            )
        return messages

    def _build_infoleg_response(
        self,
        question: str,
        legal_res: ArgentinaDataLegalResult,
        threshold: float,
        local_score: float,
        history: Optional[List[ChatTurn]] = None,
    ) -> ChatResponse:
        """Construye una respuesta estructurada trazable a partir de la legislación InfoLEG."""
        citations: List[SourceCitation] = [
            SourceCitation(
                source_file=f"InfoLEG ({legal_res.norma_ref})",
                document_title=f"{legal_res.cita} — {legal_res.titulo}",
                category="Legislación Nacional (InfoLEG)",
                page=None,
                article_hint=art.unidad.title(),
                relevance_score=0.85,
                excerpt=art.texto if len(art.texto) <= 320 else art.texto[:317] + "...",
            )
            for art in legal_res.articulos
        ]

        if _has_real_api_key():
            context_blocks = [
                f"[FUENTE OFICIAL INFOLEG] {legal_res.cita}: {legal_res.titulo}\n"
                f"Referencia: {legal_res.norma_ref} | Versión: {legal_res.version} | Estado vigencia: {legal_res.estado_vigencia}\n"
                f"Enlace oficial: {legal_res.url}\n"
                + (f"Aviso de vigencia: {legal_res.aviso_vigencia}\n" if legal_res.aviso_vigencia else "")
                + "Artículos recuperados:\n"
                + "\n\n".join(f"- {art.unidad.upper()}: {art.texto}" for art in legal_res.articulos)
            ]
            context_text = "\n\n".join(context_blocks)
            if self._llm is None:
                self._llm = build_llm()
            chain = AGORA_RAG_PROMPT | self._llm | StrOutputParser()
            answer = chain.invoke(
                {
                    "context": context_text,
                    "question": question,
                    "history": self._history_messages(history),
                }
            )
            if legal_res.url not in answer:
                answer += f"\n\n🔗 **Fuente oficial en InfoLEG:** [{legal_res.cita}]({legal_res.url})"
            if legal_res.version == "original" and "modificaci" not in answer.lower():
                answer += f"\n\n> ⚠️ *Nota sobre vigencia:* Texto recuperado en versión original. Consultar [InfoLEG]({legal_res.url}) para verificar modificaciones posteriores."
        else:
            answer = _synthesize_infoleg_offline_answer(question, legal_res)

        structured = parse_structured_sections(answer)
        return ChatResponse(
            bot_name=CHATBOT_NAME,
            question=question,
            answer=answer,
            is_grounded=True,
            max_relevance_score=0.85,
            threshold_used=threshold,
            structured_sections=structured,
            sources=citations,
            response_type="grounded",
            retrieval_query=None,
            related_cases=[],
        )

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        history: Optional[List[ChatTurn]] = None,
    ) -> ChatResponse:
        """Ejecuta el pipeline completo RAG con corte preventivo Cero Alucinaciones."""
        threshold = (
            score_threshold
            if score_threshold is not None
            else settings.similarity_score_threshold
        )

        def _simple(answer: str, rtype: str, grounded: bool = False, score: float = 0.0) -> ChatResponse:
            return ChatResponse(
                bot_name=CHATBOT_NAME,
                question=question,
                answer=answer,
                is_grounded=grounded,
                max_relevance_score=round(score, 4),
                threshold_used=threshold,
                structured_sections=None,
                sources=[],
                response_type=rtype,  # type: ignore[arg-type]
            )

        # Seguridad: bloquear intentos de manipular el prompt antes de cualquier búsqueda o LLM
        if detect_prompt_injection(question):
            return _simple(BLOCKED_RESPONSE, "blocked")

        # Saludos y preguntas sobre el propio bot: no requieren recuperación
        if is_smalltalk(question):
            return _simple(GREETING_RESPONSE, "smalltalk")

        indexed_count = self.get_indexed_chunks_count()
        if indexed_count == 0:
            return _simple(
                f"La base vectorial de {CHATBOT_NAME} aún no contiene documentos indexados. "
                "Ejecuta la ingesta (`POST /api/ingest` o `python ingest_cli.py`) para procesar "
                "los PDFs normativos antes de realizar consultas.",
                "no_info",
            )

        # Si es un seguimiento explícito ("eso", "también"...), se contextualiza con el turno
        # previo del usuario; si no produce resultados, se reintenta con la consulta sola.
        followup_query = self._build_followup_query(question, history)
        candidate_queries = [followup_query, question] if followup_query else [question]
        retrieval_query = question
        relevant_docs: List[Tuple[Document, float]] = []
        max_score, effective_threshold = 0.0, threshold
        for candidate in candidate_queries:
            relevant_docs, max_score, effective_threshold = self.retrieve_with_threshold(
                query=candidate,
                k=top_k,
                score_threshold=score_threshold,
            )
            if relevant_docs:
                retrieval_query = candidate
                break

        # Regla estricta: Cero Alucinaciones — cortar antes de invocar al LLM si no supera el umbral
        if not relevant_docs:
            # Módulo complementario Argentina Data MCP: consultar exclusivamente cuando no se alcanza el umbral local
            legal_result = argentina_data_client.query_legal_fallback(question)
            if legal_result and legal_result.articulos:
                return self._build_infoleg_response(
                    question=question,
                    legal_res=legal_result,
                    threshold=effective_threshold,
                    local_score=max_score,
                    history=history,
                )
            return _simple(OUT_OF_DOMAIN_RESPONSE, "no_info", score=max_score)

        if _has_real_api_key():
            context_block = self._format_context(relevant_docs)
            if self._llm is None:
                self._llm = build_llm()
            chain = AGORA_RAG_PROMPT | self._llm | StrOutputParser()
            answer = chain.invoke(
                {
                    "context": context_block,
                    "question": question,
                    "history": self._history_messages(history),
                }
            )
        else:
            answer = _synthesize_grounded_offline_answer(question, relevant_docs)

        structured = parse_structured_sections(answer)
        citations = self._to_source_citations(relevant_docs)
        related = find_related_cases(
            [c.source_file for c in citations], question
        )

        return ChatResponse(
            bot_name=CHATBOT_NAME,
            question=question,
            answer=answer,
            is_grounded=True,
            max_relevance_score=round(max_score, 4),
            threshold_used=effective_threshold,
            structured_sections=structured,
            sources=citations,
            response_type="grounded",
            retrieval_query=retrieval_query if retrieval_query != question else None,
            related_cases=related,
        )


rag_pipeline = AgoraRAGPipeline()
