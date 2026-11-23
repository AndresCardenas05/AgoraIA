"""Configuración centralizada y catálogo normativo de ÁgoraIA."""

from pathlib import Path
from typing import Dict, List, Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class DocumentMetadataEntry:
    """Metadatos oficiales asociados a un documento PDF del corpus normativo."""

    def __init__(
        self,
        filename: str,
        title: str,
        category: str,
        short_citation: str,
        description: str,
    ) -> None:
        self.filename = filename
        self.title = title
        self.category = category
        self.short_citation = short_citation
        self.description = description


DOCUMENT_CATALOG: Dict[str, DocumentMetadataEntry] = {
    "1_constitucion_de_la_nacion_argentina.pdf": DocumentMetadataEntry(
        filename="1_constitucion_de_la_nacion_argentina.pdf",
        title="Constitución de la Nación Argentina",
        category="Constitucional",
        short_citation="Constitución Nacional (Arts. 14, 19, 32, 43, 75 inc. 19 y 22)",
        description="Libertad de prensa sin censura previa, principio de privacidad, habeas data y secreto de las fuentes periodísticas.",
    ),
    "3_servicios-de-comunicacion-audiovisual-ley-26522.pdf": DocumentMetadataEntry(
        filename="3_servicios-de-comunicacion-audiovisual-ley-26522.pdf",
        title="Ley 26.522 de Servicios de Comunicación Audiovisual y Dec. 1225/2010",
        category="Legislación Nacional",
        short_citation="Ley 26.522 (SCA)",
        description="Pluralismo, diversidad, interés público de la comunicación, derechos de las audiencias, protección de la niñez y principios éticos.",
    ),
    "4_ley11723.pdf": DocumentMetadataEntry(
        filename="4_ley11723.pdf",
        title="Ley 11.723 de Régimen Legal de la Propiedad Intelectual",
        category="Legislación Nacional",
        short_citation="Ley 11.723 (Propiedad Intelectual)",
        description="Derechos de autor sobre obras periodísticas, derecho de cita, colaboraciones, retratos y compilaciones de bases de datos.",
    ),
    "6_ley_d_eporteccion_de_datos_arg_ley25326.pdf": DocumentMetadataEntry(
        filename="6_ley_d_eporteccion_de_datos_arg_ley25326.pdf",
        title="Ley 25.326 de Protección de los Datos Personales",
        category="Legislación Nacional",
        short_citation="Ley 25.326 (Habeas Data / Datos Personales)",
        description="Datos sensibles, licitud y consentimiento informado, disociación, perfilado automatizado y resguardo de fuentes periodísticas.",
    ),
    "7_trabajo_periodistico.pdf": DocumentMetadataEntry(
        filename="7_trabajo_periodistico.pdf",
        title="Ley 12.908 — Estatuto del Periodista Profesional",
        category="Legislación Nacional",
        short_citation="Ley 12.908 (Estatuto del Periodista)",
        description="Definición del rol periodístico, libertad de prensa y pensamiento como derechos inalienables y acceso libre a fuentes de interés público.",
    ),
    "11_IA_y-medios-argentinos-2026.pdf": DocumentMetadataEntry(
        filename="11_IA_y-medios-argentinos-2026.pdf",
        title="Informe ADEPA 2026: Inteligencia Artificial y Medios Argentinos",
        category="Gobernanza IA / ADEPA",
        short_citation="Informe ADEPA 2026 (Adopción, Gobernanza y Sostenibilidad)",
        description="Principios de Consentimiento, Compensación y Cita; human-in-the-loop; entornos zero-click/GEO y litigios sobre derechos de autor.",
    ),
    "12_guia-para-el-uso-de-la-ia-en-los-medios-argentinos.pdf": DocumentMetadataEntry(
        filename="12_guia-para-el-uso-de-la-ia-en-los-medios-argentinos.pdf",
        title="Guía ADEPA para el uso de la IA en los medios argentinos",
        category="Gobernanza IA / ADEPA",
        short_citation="Guía ADEPA de IA en Medios (8 Principios)",
        description="Ocho recomendaciones rectoras sobre supervisión humana, transparencia explícita, mitigación de sesgos y respeto al copyright.",
    ),
    "Normas_argentinas_ejercicio_periodistico.pdf": DocumentMetadataEntry(
        filename="Normas_argentinas_ejercicio_periodistico.pdf",
        title="Cuadro Resumen: Normas Argentinas del Ejercicio Periodístico",
        category="Síntesis Normativa",
        short_citation="Síntesis Normativa (Leyes 26.032, 27.078, Disp. 2/2023, Res. AAIP 161/2023)",
        description="Compendio de marcos constitucionales, legales y éticos aplicables al periodismo digital, streaming e inteligencia artificial en Argentina.",
    ),
}


class Settings(BaseSettings):
    """Configuración tipada cargada desde variables de entorno y .env."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ÁgoraIA"
    app_version: str = "1.0.0"
    environment: str = "development"

    # Proveedor LLM
    llm_provider: Literal["openai", "gemini"] = "openai"
    openai_llm_model: str = "gpt-4o-mini"
    gemini_llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = Field(default=0.2, ge=0.0, le=1.0)

    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    # Proveedor de Embeddings
    embedding_provider: Literal["huggingface", "openai"] = "huggingface"
    huggingface_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    openai_embedding_model: str = "text-embedding-3-small"

    # Chunking y recuperación
    chunk_size: int = Field(default=1000, ge=200, le=4000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_score_threshold: float = Field(default=0.45, ge=0.0, le=1.0)

    # Rutas y ChromaDB
    chroma_collection_name: str = "agora_ia_etica_periodistica"
    pdf_directory: str = "./data/pdfs"
    chroma_persist_directory: str = "./data/chroma_db"

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Integración complementaria: Argentina Data MCP (Legislación InfoLEG)
    argentina_data_api_key: Optional[str] = None
    argentina_data_base_url: str = "https://argentinadata.mymcps.dev/api/v1"
    argentina_data_timeout_seconds: float = 6.0

    @property
    def pdf_dir_path(self) -> Path:
        path = Path(self.pdf_directory)
        return path if path.is_absolute() else (BASE_DIR / path).resolve()

    @property
    def chroma_dir_path(self) -> Path:
        path = Path(self.chroma_persist_directory)
        return path if path.is_absolute() else (BASE_DIR / path).resolve()

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
