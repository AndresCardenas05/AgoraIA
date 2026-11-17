"""Pipeline de ingesta de PDFs, chunking legal coherente y vectorización en ChromaDB (con respaldo coseno local)."""

import importlib.util
import json
import math
import re
import shutil
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import DOCUMENT_CATALOG, settings


LEGAL_SEPARATORS: List[str] = [
    "\nARTÍCULO ",
    "\nArtículo ",
    "\nArt. ",
    "\nCAPÍTULO ",
    "\nCapítulo ",
    "\nHallazgo ",
    "\nPrincipio ",
    "\n\n",
    "\n",
    ". ",
    " ",
    "",
]

ARTICLE_PATTERN = re.compile(
    r"(?:ART[ÍI]CULO|Art[íi]culo|Art\.?|Hallazgo|Principio|Recomendaci[óo]n|Inciso)\s*"
    r"(\d+[°º]?(?:\s*(?:bis|ter|inc\.?\s*[a-z0-9]+))?)",
    re.IGNORECASE,
)

SPANISH_STOPWORDS = {
    "a", "acerca", "al", "algo", "algunas", "algunos", "ante", "aplica", "aplican",
    "aquel", "aquella", "aquellas", "aquellos", "aqui", "asi", "aun", "bajo", "bien",
    "cada", "caso", "casi", "como", "con", "contra", "cual", "cuales", "cuando",
    "cuanto", "de", "del", "desde", "donde", "dos", "el", "ella", "ellas", "ello",
    "ellos", "en", "entre", "era", "eran", "es", "esa", "esas", "ese", "eso",
    "esos", "esta", "estaba", "estan", "estas", "este", "esto", "estos", "fue",
    "fueron", "ha", "haber", "habia", "hace", "hacer", "hacia", "han", "hasta",
    "hay", "hecho", "la", "las", "le", "les", "lo", "los", "mas", "me", "mi",
    "mientras", "misma", "mismo", "muy", "ni", "no", "nos", "nosotros", "nuestra",
    "nuestro", "o", "otra", "otras", "otro", "otros", "para", "pero", "por",
    "porque", "puede", "pueden", "que", "quien", "quienes", "se", "sea", "segun",
    "ser", "si", "sin", "sobre", "solo", "son", "su", "sus", "tal", "tambien",
    "tan", "tanto", "te", "tendria", "tiene", "tienen", "toda", "todas", "todo",
    "todos", "tras", "tu", "tus", "un", "una", "unas", "uno", "unos", "utiliza",
    "va", "vamos", "varios", "y", "ya", "yo",
}

LOCAL_INDEX_FILENAME = "local_index.json"


def _normalize_text(text: str) -> str:
    """Normaliza tildes y convierte texto a minúsculas ASCII."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _light_spanish_stem(token: str) -> str:
    """Aplica recorte morfológico ligero para términos legales/periodísticos en español."""
    if len(token) <= 4 or token.isdigit():
        return token
    if token.endswith("ces") and len(token) >= 5:
        return token[:-3] + "z"
    for suffix in (
        "amientos", "amiento", "aciones", "acion", "uciones", "ucion",
        "idades", "idad", "isticas", "istico", "isticos", "istica",
        "mente", "adoras", "adores", "adora", "ador",
        "ciones", "cion", "siones", "sion", "encias", "encia",
        "anzas", "anza", "ibles", "ible", "ables", "able",
        "ados", "adas", "ado", "ada", "idos", "idas", "ido", "ida",
        "es", "as", "os", "s",
    ):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def tokenize_spanish(text: str) -> List[str]:
    """Tokeniza un texto en español generando raíces normalizadas y bigramas."""
    norm = _normalize_text(text)
    raw_tokens = re.findall(r"[a-z0-9]{2,}", norm)
    stems = [
        _light_spanish_stem(tok)
        for tok in raw_tokens
        if tok not in SPANISH_STOPWORDS and len(tok) >= 2
    ]
    bigrams = [f"{stems[i]}_{stems[i + 1]}" for i in range(len(stems) - 1)]
    return stems + bigrams


# Vocabulario ancla del dominio: una consulta debe contener al menos uno de estos
# términos para que el índice léxico de respaldo la considere del dominio. Esto evita
# que palabras comunes ("capital", "habitantes") hagan coincidir preguntas ajenas.
DOMAIN_ANCHOR_WORDS = [
    "periodismo", "periodista", "periodistas", "periodistico", "periodisticos", "prensa", "medio",
    "medios", "noticia", "noticias", "noticiero", "informacion", "informativo", "informativos",
    "comunicacion", "audiovisual", "audiencia", "audiencias", "publicidad", "publicacion",
    "censura", "libertad", "expresion", "ley", "leyes", "articulo", "articulos", "art",
    "constitucion", "constitucional", "decreto", "norma", "normas", "normativa", "legal",
    "derecho", "derechos", "autor", "autoria", "copyright", "propiedad", "intelectual",
    "plagio", "cita", "citar", "datos", "dato", "personal", "personales", "sensible",
    "sensibles", "privacidad", "intimidad", "honor", "habeas", "consentimiento", "fuente",
    "fuentes", "secreto", "ia", "inteligencia", "artificial", "generativa", "generativo",
    "algoritmo", "chatbot", "scraping", "buscador", "buscadores", "adepa", "etica", "etico",
    "eticos", "deontologia", "transparencia", "veracidad", "verificacion", "desinformacion",
    "supervision", "ninez", "nino", "ninos", "menor", "menores", "adolescente", "adolescentes",
    "imagen", "retrato", "voz", "deepfake", "clonar", "clonacion", "compensacion", "licencia",
    "estatuto", "redaccion", "editorial", "diario", "periodico", "medio", "dilema", "dilemas",
    "robots", "zero", "geo", "seo", "plataforma", "plataformas", "openai", "microsoft",
    "human", "loop", "gobernanza", "discriminacion", "pluralismo", "defensoria",
]

DOMAIN_ANCHOR_STEMS = {
    _light_spanish_stem(_normalize_text(word)) for word in DOMAIN_ANCHOR_WORDS
}


def has_domain_anchor(query: str) -> bool:
    """Indica si la consulta contiene vocabulario propio del dominio."""
    return any(
        tok in DOMAIN_ANCHOR_STEMS for tok in tokenize_spanish(query) if "_" not in tok
    )


class LocalCosineVectorStore:
    """Almacén vectorial local persistente con similitud coseno TF-IDF como respaldo de ChromaDB."""

    def __init__(self, persist_directory: Path) -> None:
        self.persist_directory = persist_directory
        self.index_path = persist_directory / LOCAL_INDEX_FILENAME
        self.records: List[Dict[str, Any]] = []
        self.idf: Dict[str, float] = {}
        self.doc_vectors: List[Dict[str, float]] = []
        if self.index_path.exists():
            self._load()

    def _load(self) -> None:
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        self.records = data.get("records", [])
        self.idf = data.get("idf", {})
        self.doc_vectors = data.get("doc_vectors", [])

    def _save(self) -> None:
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": self.records,
            "idf": self.idf,
            "doc_vectors": self.doc_vectors,
        }
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def _rebuild_vectors(self) -> None:
        n_docs = len(self.records)
        if n_docs == 0:
            self.idf = {}
            self.doc_vectors = []
            return

        doc_tokens: List[List[str]] = []
        df: Counter[str] = Counter()
        for rec in self.records:
            meta = rec.get("metadata", {})
            header_ctx = f"{meta.get('document_title', '')} {meta.get('article_hint', '')}"
            tokens = tokenize_spanish(f"{header_ctx} {rec['page_content']}")
            doc_tokens.append(tokens)
            for term in set(tokens):
                df[term] += 1

        self.idf = {
            term: math.log((n_docs + 1.0) / (freq + 1.0)) + 1.0
            for term, freq in df.items()
        }

        vectors: List[Dict[str, float]] = []
        for tokens in doc_tokens:
            counts = Counter(tokens)
            vec: Dict[str, float] = {}
            norm_sq = 0.0
            for term, tf in counts.items():
                w = (1.0 + math.log(tf)) * self.idf.get(term, 1.0)
                vec[term] = w
                norm_sq += w * w
            norm = math.sqrt(norm_sq) or 1.0
            vectors.append({term: w / norm for term, w in vec.items()})
        self.doc_vectors = vectors

    def add_documents(self, docs: List[Document]) -> None:
        for doc in docs:
            self.records.append(
                {
                    "page_content": doc.page_content,
                    "metadata": dict(doc.metadata),
                }
            )
        self._rebuild_vectors()
        self._save()

    def count(self) -> int:
        return len(self.records)

    def similarity_search_with_relevance_scores(
        self, query: str, k: int = 5
    ) -> List[Tuple[Document, float]]:
        """Calcula similitud coseno TF-IDF normalizada con penalización real a términos OOV."""
        if not self.records:
            return []

        q_tokens = tokenize_spanish(query)
        if not q_tokens or not has_domain_anchor(query):
            return []

        oov_idf = 6.0
        q_counts = Counter(q_tokens)
        q_vec: Dict[str, float] = {}
        q_norm_sq = 0.0
        q_unigram_terms: List[str] = []
        q_unigram_idfs: List[float] = []

        for term, tf in q_counts.items():
            is_bigram = "_" in term
            in_vocab = term in self.idf
            if is_bigram and not in_vocab:
                continue

            idf_val = self.idf.get(term, oov_idf)
            w = (1.0 + math.log(tf)) * idf_val * (0.6 if is_bigram else 1.0)
            q_vec[term] = w
            q_norm_sq += w * w

            if not is_bigram:
                q_unigram_terms.append(term)
                q_unigram_idfs.append(idf_val)

        effective_q_idf = sum(sorted(q_unigram_idfs, reverse=True)[:6])
        if not q_vec or q_norm_sq == 0.0 or effective_q_idf == 0.0:
            return []

        q_norm = math.sqrt(q_norm_sq)
        q_unit = {term: w / q_norm for term, w in q_vec.items()}

        scored: List[Tuple[int, float]] = []
        for idx, d_vec in enumerate(self.doc_vectors):
            cosine = sum(q_unit[t] * d_vec[t] for t in q_unit if t in d_vec)
            if cosine <= 0.0:
                continue

            matched_unigrams = [t for t in q_unigram_terms if t in d_vec]
            if not matched_unigrams:
                continue

            matched_idf = sum(self.idf[t] for t in matched_unigrams if t in self.idf)
            idf_recall = min(1.0, matched_idf / effective_q_idf)

            # Calibración monotónica: requiere coincidencia múltiple y cobertura real de consulta
            raw_score = 0.35 * cosine + 0.65 * idf_recall
            if len(q_unigram_terms) >= 3 and len(matched_unigrams) < 2:
                raw_score *= 0.15

            relevance = min(0.98, raw_score * 2.15)
            scored.append((idx, relevance))

        scored.sort(key=lambda item: item[1], reverse=True)
        results: List[Tuple[Document, float]] = []
        for idx, score in scored[:k]:
            rec = self.records[idx]
            results.append(
                (
                    Document(
                        page_content=rec["page_content"],
                        metadata=dict(rec.get("metadata", {})),
                    ),
                    round(float(score), 4),
                )
            )
        return results


def _module_available(name: str) -> bool:
    """Comprueba si un módulo opcional está instalado sin importarlo."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def is_chroma_available() -> bool:
    """Indica si ChromaDB y el proveedor de embeddings configurado están disponibles."""
    required = ["chromadb", "langchain_chroma"]
    if settings.embedding_provider == "openai":
        key = settings.openai_api_key
        if not key or key.startswith("sk-reemplazar"):
            return False
        required.append("langchain_openai")
    else:
        required.extend(["langchain_huggingface", "sentence_transformers"])
    return all(_module_available(mod) for mod in required)


def build_embeddings() -> Embeddings:
    """Construye el modelo de embeddings multilingüe/español según configuración."""
    if settings.embedding_provider == "openai":
        if not settings.openai_api_key or settings.openai_api_key.startswith("sk-reemplazar"):
            raise ValueError(
                "OPENAI_API_KEY válido es obligatorio cuando EMBEDDING_PROVIDER='openai'."
            )
        from langchain_openai import OpenAIEmbeddings
        from pydantic import SecretStr

        return OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=SecretStr(settings.openai_api_key),
        )

    from langchain_huggingface import HuggingFaceEmbeddings  # type: ignore[import-not-found]

    return HuggingFaceEmbeddings(
        model_name=settings.huggingface_embedding_model,
        encode_kwargs={"normalize_embeddings": True},
    )


def extract_article_hint(text: str) -> Optional[str]:
    """Extrae una referencia breve al primer artículo, principio o hallazgo hallado."""
    match = ARTICLE_PATTERN.search(text)
    if not match:
        return None
    return " ".join(match.group(0).split())[:60]


class KnowledgeBaseIngestor:
    """Gestiona la lectura de PDFs, fragmentación legal e indexación vectorial."""

    def __init__(self, embeddings: Optional[Embeddings] = None) -> None:
        self._embeddings = embeddings
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=LEGAL_SEPARATORS,
            keep_separator=True,
            strip_whitespace=True,
        )

    def _enrich_document_metadata(self, doc: Document, pdf_path: Path) -> Document:
        """Agrega metadatos normativos oficiales y número de página base 1."""
        filename = pdf_path.name
        catalog_entry = DOCUMENT_CATALOG.get(filename)

        raw_page = doc.metadata.get("page", 0)
        page_number = int(raw_page) + 1 if isinstance(raw_page, int) else 1

        doc.metadata["source_file"] = filename
        doc.metadata["page"] = page_number
        if catalog_entry:
            doc.metadata["document_title"] = catalog_entry.title
            doc.metadata["category"] = catalog_entry.category
            doc.metadata["short_citation"] = catalog_entry.short_citation
        else:
            doc.metadata["document_title"] = pdf_path.stem.replace("_", " ").title()
            doc.metadata["category"] = "Documentación Complementaria"
            doc.metadata["short_citation"] = filename

        return doc

    def _load_single_pdf(self, pdf_path: Path) -> List[Document]:
        """Usa PyPDFLoader cuando está disponible, con respaldo directo en pypdf."""
        try:
            from langchain_community.document_loaders import PyPDFLoader

            loader = PyPDFLoader(str(pdf_path))
            return loader.load()
        except Exception:
            from pypdf import PdfReader

            reader = PdfReader(str(pdf_path))
            docs: List[Document] = []
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    docs.append(
                        Document(
                            page_content=text,
                            metadata={"source": str(pdf_path), "page": idx},
                        )
                    )
            return docs

    def load_pdfs(self, pdf_dir: Optional[Path] = None) -> Tuple[List[Document], int]:
        """Carga todas las páginas de los archivos PDF disponibles en el directorio."""
        target_dir = pdf_dir or settings.pdf_dir_path
        if not target_dir.exists():
            raise FileNotFoundError(
                f"El directorio de PDFs no existe: {target_dir}"
            )

        pdf_files = sorted(target_dir.glob("*.pdf"))
        if not pdf_files:
            raise FileNotFoundError(
                f"No se encontraron archivos PDF en {target_dir}"
            )

        all_pages: List[Document] = []
        for pdf_path in pdf_files:
            pages = self._load_single_pdf(pdf_path)
            for page_doc in pages:
                raw_text = re.sub(
                    r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ])-\s*\n\s*([a-záéíóúüñ])",
                    r"\1\2",
                    page_doc.page_content,
                )
                cleaned_text = re.sub(r"[ \t]+", " ", raw_text).strip()
                if not cleaned_text:
                    continue
                page_doc.page_content = cleaned_text
                all_pages.append(self._enrich_document_metadata(page_doc, pdf_path))

        return all_pages, len(pdf_files)

    def split_documents(self, pages: List[Document]) -> List[Document]:
        """Divide los documentos respetando separadores de artículos y agrega pistas."""
        chunks = self.text_splitter.split_documents(pages)
        enriched_chunks: List[Document] = []

        for idx, chunk in enumerate(chunks):
            article_hint = extract_article_hint(chunk.page_content)
            chunk.metadata["chunk_index"] = idx
            if article_hint:
                chunk.metadata["article_hint"] = article_hint
            enriched_chunks.append(chunk)

        return enriched_chunks

    def ingest_all(self, reset: bool = False) -> Dict[str, Any]:
        """Ejecuta el pipeline completo de ingesta hacia ChromaDB o el índice coseno local."""
        persist_dir = settings.chroma_dir_path
        persist_dir.mkdir(parents=True, exist_ok=True)
        if reset:
            for item in persist_dir.iterdir():
                if item.name == ".gitkeep":
                    continue
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)

        pages, files_processed = self.load_pdfs()
        chunks = self.split_documents(pages)

        backend_used = "local_cosine_tfidf"
        if is_chroma_available():
            try:
                from langchain_chroma import Chroma  # type: ignore[import-not-found]

                embeddings = self._embeddings or build_embeddings()
                vectorstore = Chroma(
                    collection_name=settings.chroma_collection_name,
                    embedding_function=embeddings,
                    persist_directory=str(persist_dir),
                    collection_metadata={"hnsw:space": "cosine"},
                )
                batch_size = 100
                for start in range(0, len(chunks), batch_size):
                    batch = chunks[start : start + batch_size]
                    vectorstore.add_documents(batch)
                backend_used = "chromadb"
            except Exception:
                local_store = LocalCosineVectorStore(persist_dir)
                local_store.add_documents(chunks)
        else:
            local_store = LocalCosineVectorStore(persist_dir)
            local_store.add_documents(chunks)

        return {
            "status": f"completed ({backend_used})",
            "files_processed": files_processed,
            "pages_loaded": len(pages),
            "chunks_indexed": len(chunks),
            "collection_name": settings.chroma_collection_name,
            "persist_directory": str(persist_dir),
        }
