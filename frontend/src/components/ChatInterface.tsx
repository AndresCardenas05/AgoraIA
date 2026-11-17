"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Scale,
  User,
  AlertOctagon,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
} from "lucide-react";
import { ChatMessage, ChatTurn } from "@/types/chat";
import { sendChatQuery, sendFeedback } from "@/lib/api";
import { StructuredResponseCard } from "./StructuredResponseCard";
import { LoadingIndicator } from "./LoadingIndicator";

interface ChatInterfaceProps {
  selectedPrompt: string;
  onPromptConsumed: () => void;
  threshold: number;
}

const MAX_HISTORY_TURNS = 6;

function nowLabel() {
  return new Date().toLocaleTimeString("es-AR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ChatInterface({
  selectedPrompt,
  onPromptConsumed,
  threshold,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (selectedPrompt) {
      setInput(selectedPrompt);
      onPromptConsumed();
    }
  }, [selectedPrompt, onPromptConsumed]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const buildHistory = useCallback((): ChatTurn[] => {
    return messages
      .filter((m) => !m.error)
      .slice(-MAX_HISTORY_TURNS)
      .map((m) => ({ role: m.role, content: m.content.slice(0, 1500) }));
  }, [messages]);

  const sendQuestion = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || isLoading) return;

      const history = buildHistory();
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: trimmed,
        timestamp: nowLabel(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setIsLoading(true);

      try {
        // Tiempo mínimo de "pensando" para que el usuario perciba el proceso de análisis
        const [response] = await Promise.all([
          sendChatQuery(trimmed, { score_threshold: threshold, history }),
          new Promise((resolve) => setTimeout(resolve, 2200)),
        ]);

        setMessages((prev) => [
          ...prev,
          {
            id: `bot-${Date.now()}`,
            role: "assistant",
            content: response.answer,
            timestamp: nowLabel(),
            responseMeta: response,
          },
        ]);
      } catch (err) {
        const errorText =
          err instanceof TypeError
            ? "No se pudo conectar con el backend de ÁgoraIA. Verifica que el servidor esté en ejecución (puerto 8000)."
            : err instanceof Error
              ? err.message
              : "Error inesperado al comunicarse con el backend de ÁgoraIA.";
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: errorText,
            timestamp: nowLabel(),
            error: errorText,
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [buildHistory, isLoading, threshold]
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    void sendQuestion(input);
  }

  async function handleFeedback(msg: ChatMessage, rating: "up" | "down") {
    if (!msg.responseMeta || msg.feedback) return;
    setMessages((prev) =>
      prev.map((m) => (m.id === msg.id ? { ...m, feedback: rating } : m))
    );
    try {
      await sendFeedback({
        question: msg.responseMeta.question,
        answer: msg.responseMeta.answer,
        rating,
        response_type: msg.responseMeta.response_type,
        max_relevance_score: msg.responseMeta.max_relevance_score,
      });
    } catch {
      // La valoración es opcional; un fallo no debe interrumpir la conversación
    }
  }

  return (
    <div className="flex h-full flex-1 flex-col bg-slate-100/50">
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-8">
        <div className="mx-auto max-w-4xl space-y-6">
          {messages.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 text-amber-400">
                <Scale className="h-7 w-7" />
              </div>
              <h2 className="font-serif text-2xl font-bold text-slate-900">
                Bienvenido a ÁgoraIA
              </h2>
              <p className="mx-auto mt-2 max-w-2xl text-sm leading-relaxed text-slate-600">
                Soy tu asistente experto en ética periodística, comunicación digital,
                legislación argentina e impacto de la IA generativa. Cada respuesta se
                estructura en 4 puntos y cita exclusivamente documentos verificados de mi
                base normativa. Puedes hacer preguntas de seguimiento: recuerdo el hilo de
                la conversación.
              </p>
              <div className="mt-6 grid gap-3 text-left sm:grid-cols-3">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs">
                  <strong className="text-slate-900">Consultar conceptos</strong>
                  <p className="mt-1 text-slate-600">
                    Definiciones y principios: datos sensibles, derecho de cita,
                    human-in-the-loop.
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs">
                  <strong className="text-slate-900">Explorar casos</strong>
                  <p className="mt-1 text-slate-600">
                    Casos del corpus como la demanda de Perfil contra OpenAI y Microsoft.
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs">
                  <strong className="text-slate-900">Analizar dilemas</strong>
                  <p className="mt-1 text-slate-600">
                    Valores en conflicto, marco normativo y recomendación fundamentada.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} className="animate-fade-in-up space-y-2">
                {msg.role === "user" ? (
                  <div className="flex items-start justify-end gap-3">
                    <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-slate-900 px-4 py-3 text-sm text-white shadow-sm">
                      <p className="leading-relaxed">{msg.content}</p>
                      <span className="mt-1 block text-right text-[10px] text-slate-400">
                        {msg.timestamp}
                      </span>
                    </div>
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-700">
                      <User className="h-4 w-4" />
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-800">
                      <Scale className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      {msg.error ? (
                        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
                          <div className="flex items-center gap-2 font-semibold">
                            <AlertOctagon className="h-4 w-4" />
                            No se pudo completar la consulta
                          </div>
                          <p className="mt-1 text-xs">{msg.error}</p>
                        </div>
                      ) : msg.responseMeta ? (
                        <StructuredResponseCard
                          response={msg.responseMeta}
                          onAsk={(q) => void sendQuestion(q)}
                        />
                      ) : (
                        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-800">
                          {msg.content}
                        </div>
                      )}
                      <div className="mt-1.5 flex items-center gap-3 text-[10px] text-slate-400">
                        <span>ÁgoraIA · {msg.timestamp}</span>
                        {msg.responseMeta?.response_type === "grounded" && (
                          <span className="flex items-center gap-1">
                            <span className="text-slate-400">¿Fue útil?</span>
                            <button
                              type="button"
                              aria-label="Respuesta útil"
                              disabled={!!msg.feedback}
                              onClick={() => void handleFeedback(msg, "up")}
                              className={`rounded p-1 transition hover:bg-emerald-50 hover:text-emerald-700 disabled:cursor-default ${
                                msg.feedback === "up" ? "text-emerald-700" : ""
                              }`}
                            >
                              <ThumbsUp className="h-3.5 w-3.5" />
                            </button>
                            <button
                              type="button"
                              aria-label="Respuesta no útil"
                              disabled={!!msg.feedback}
                              onClick={() => void handleFeedback(msg, "down")}
                              className={`rounded p-1 transition hover:bg-rose-50 hover:text-rose-700 disabled:cursor-default ${
                                msg.feedback === "down" ? "text-rose-700" : ""
                              }`}
                            >
                              <ThumbsDown className="h-3.5 w-3.5" />
                            </button>
                            {msg.feedback && (
                              <span className="text-emerald-700">Gracias por tu valoración</span>
                            )}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}

          {isLoading && <LoadingIndicator />}

          <div ref={bottomRef} />
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-slate-200 bg-white px-4 py-4 sm:px-8"
      >
        <div className="mx-auto flex max-w-4xl items-end gap-3">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={() => setMessages([])}
              disabled={isLoading}
              title="Iniciar una nueva conversación"
              className="inline-flex h-11 items-center gap-1.5 rounded-xl border border-slate-300 px-3 text-xs font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Nueva</span>
            </button>
          )}
          <textarea
            rows={2}
            value={input}
            maxLength={4000}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void sendQuestion(input);
              }
            }}
            placeholder="Plantea un dilema ético, caso periodístico o consulta sobre IA y legislación argentina..."
            className="flex-1 resize-none rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:bg-white focus:outline-none"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="inline-flex h-11 items-center gap-2 rounded-xl bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            <span className="hidden sm:inline">Analizar</span>
          </button>
        </div>
      </form>
    </div>
  );
}
