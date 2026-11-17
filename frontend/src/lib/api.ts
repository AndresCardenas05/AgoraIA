import {
  CaseInfo,
  ChatResponse,
  ChatTurn,
  HealthResponse,
  IngestResponse,
  SourcesListResponse,
  StructuredAnalysis,
} from "@/types/chat";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function handleApiResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Error HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) {
        detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // Mantiene el mensaje HTTP genérico si el cuerpo no es JSON
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/health`, {
    cache: "no-store",
  });
  return handleApiResponse<HealthResponse>(res);
}

export async function fetchSources(): Promise<SourcesListResponse> {
  const res = await fetch(`${API_BASE_URL}/api/sources`, {
    cache: "no-store",
  });
  return handleApiResponse<SourcesListResponse>(res);
}

export async function triggerIngest(reset = false): Promise<IngestResponse> {
  const res = await fetch(`${API_BASE_URL}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reset }),
  });
  return handleApiResponse<IngestResponse>(res);
}

export async function sendChatQuery(
  question: string,
  options?: { top_k?: number; score_threshold?: number; history?: ChatTurn[] }
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      top_k: options?.top_k,
      score_threshold: options?.score_threshold,
      history: options?.history ?? [],
    }),
  });
  return handleApiResponse<ChatResponse>(res);
}

export async function fetchCases(): Promise<CaseInfo[]> {
  const res = await fetch(`${API_BASE_URL}/api/cases`, { cache: "no-store" });
  return handleApiResponse<CaseInfo[]>(res);
}

export async function sendFeedback(payload: {
  question: string;
  answer: string;
  rating: "up" | "down";
  response_type: string;
  max_relevance_score: number;
}): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await handleApiResponse<{ status: string }>(res);
}

/**
 * Parser de respaldo en frontend por si el backend devuelve texto sin secciones pre-parseadas.
 */
export function extractStructuredSectionsFallback(
  answer: string
): StructuredAnalysis | null {
  const pattern =
    /(?:^|\n)\s*(?:#{1,4}\s*)?(?:\*\*)?(1\.\s*(?:\*\*)?Identificaci[óo]n del Dilema|2\.\s*(?:\*\*)?Marco Normativo\s*\/?\s*Base de Conocimiento|3\.\s*(?:\*\*)?An[áa]lisis de la Situaci[óo]n|4\.\s*(?:\*\*)?Conclusi[óo]n o Recomendaci[óo]n)[:\*]*\s*/gi;

  const matches = Array.from(answer.matchAll(pattern));
  if (matches.length < 2) {
    return null;
  }

  const map: Record<string, string> = { "1": "", "2": "", "3": "", "4": "" };
  matches.forEach((m, i) => {
    const key = m[1].trim()[0];
    const start = (m.index ?? 0) + m[0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index ?? answer.length : answer.length;
    map[key] = answer.slice(start, end).trim();
  });

  return {
    identificacion_dilema: map["1"],
    marco_normativo: map["2"],
    analisis_situacion: map["3"],
    conclusion_recomendacion: map["4"],
  };
}
