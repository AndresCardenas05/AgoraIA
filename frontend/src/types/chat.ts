export interface SourceCitation {
  source_file: string;
  document_title: string;
  category: string;
  page?: number | null;
  article_hint?: string | null;
  relevance_score: number;
  excerpt: string;
}

export interface StructuredAnalysis {
  identificacion_dilema: string;
  marco_normativo: string;
  analisis_situacion: string;
  conclusion_recomendacion: string;
}

export interface CaseInfo {
  id: string;
  title: string;
  category: string;
  summary: string;
  prompt: string;
}

export type ResponseType = "grounded" | "no_info" | "smalltalk" | "blocked";

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  bot_name: string;
  question: string;
  answer: string;
  is_grounded: boolean;
  max_relevance_score: number;
  threshold_used: number;
  structured_sections?: StructuredAnalysis | null;
  sources: SourceCitation[];
  response_type: ResponseType;
  retrieval_query?: string | null;
  related_cases: CaseInfo[];
}

export interface KnowledgeSourceInfo {
  filename: string;
  title: string;
  category: string;
  short_citation: string;
  description: string;
  exists_on_disk: boolean;
  file_size_bytes: number;
}

export interface SourcesListResponse {
  bot_name: string;
  total_documents: number;
  indexed_chunks: number;
  sources: KnowledgeSourceInfo[];
}

export interface HealthResponse {
  status: string;
  bot_name: string;
  version: string;
  llm_provider: string;
  embedding_provider: string;
  score_threshold: number;
  indexed_chunks: number;
  pdfs_available: number;
}

export interface IngestResponse {
  status: string;
  files_processed: number;
  pages_loaded: number;
  chunks_indexed: number;
  collection_name: string;
  persist_directory: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  responseMeta?: ChatResponse;
  error?: string;
  feedback?: "up" | "down";
}
