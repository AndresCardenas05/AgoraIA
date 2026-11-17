"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import {
  AlertTriangle,
  Scale,
  BookText,
  GitBranch,
  CheckCircle2,
  ShieldAlert,
  ShieldX,
  MessageSquareHeart,
  Sparkles,
  CornerDownRight,
} from "lucide-react";
import { ChatResponse } from "@/types/chat";
import { extractStructuredSectionsFallback } from "@/lib/api";
import { SourceCitations } from "./SourceCitations";

interface StructuredResponseCardProps {
  response: ChatResponse;
  onAsk?: (question: string) => void;
}

const SECTION_CONFIG = [
  {
    key: "identificacion_dilema" as const,
    number: "1",
    title: "Identificación del Dilema",
    subtitle: "Principios éticos o normativos en tensión",
    icon: AlertTriangle,
    borderColor: "border-l-amber-500",
    badgeClass: "bg-amber-100 text-amber-800",
  },
  {
    key: "marco_normativo" as const,
    number: "2",
    title: "Marco Normativo / Base de Conocimiento",
    subtitle: "Leyes, artículos, estatutos y guías ADEPA citadas",
    icon: BookText,
    borderColor: "border-l-slate-800",
    badgeClass: "bg-slate-200 text-slate-800",
  },
  {
    key: "analisis_situacion" as const,
    number: "3",
    title: "Análisis de la Situación",
    subtitle: "Posibles caminos y consecuencias éticas",
    icon: GitBranch,
    borderColor: "border-l-sky-600",
    badgeClass: "bg-sky-100 text-sky-800",
  },
  {
    key: "conclusion_recomendacion" as const,
    number: "4",
    title: "Conclusión o Recomendación",
    subtitle: "Síntesis reflexiva y buena práctica profesional",
    icon: CheckCircle2,
    borderColor: "border-l-emerald-600",
    badgeClass: "bg-emerald-100 text-emerald-800",
  },
];

export function StructuredResponseCard({
  response,
  onAsk,
}: StructuredResponseCardProps) {
  if (response.response_type === "smalltalk") {
    return (
      <div className="animate-fade-in-up rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-800 shadow-sm">
        <div className="mb-2 flex items-center gap-2 font-semibold text-slate-900">
          <MessageSquareHeart className="h-5 w-5 text-amber-600" />
          Asistente {response.bot_name}
        </div>
        <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed">
          <ReactMarkdown>{response.answer}</ReactMarkdown>
        </div>
      </div>
    );
  }

  if (response.response_type === "blocked") {
    return (
      <div className="animate-fade-in-up rounded-2xl border border-rose-300 bg-rose-50/90 p-4 text-sm text-slate-800 shadow-sm">
        <div className="mb-2 flex items-center gap-2 font-semibold text-rose-900">
          <ShieldX className="h-5 w-5 text-rose-700" />
          Solicitud Bloqueada por Seguridad (Guardrail Anti-Injection)
        </div>
        <div className="prose prose-sm max-w-none text-rose-900">
          <ReactMarkdown>{response.answer}</ReactMarkdown>
        </div>
      </div>
    );
  }

  if (!response.is_grounded) {
    return (
      <div className="animate-fade-in-up rounded-2xl border border-amber-300 bg-amber-50/80 p-4 text-sm text-slate-800 shadow-sm">
        <div className="mb-2 flex items-center gap-2 font-semibold text-amber-900">
          <ShieldAlert className="h-5 w-5 text-amber-700" />
          Regla &ldquo;Cero Alucinaciones&rdquo; Activada
        </div>
        <div className="prose prose-sm max-w-none text-slate-700">
          <ReactMarkdown>{response.answer}</ReactMarkdown>
        </div>
        <p className="mt-3 text-xs text-amber-800">
          Similitud máxima alcanzada:{" "}
          <strong>{(response.max_relevance_score * 100).toFixed(1)}%</strong> · Umbral
          requerido: <strong>{(response.threshold_used * 100).toFixed(1)}%</strong>
        </p>
      </div>
    );
  }

  const sections =
    response.structured_sections ||
    extractStructuredSectionsFallback(response.answer);

  const hasStructuredContent =
    sections &&
    (sections.identificacion_dilema ||
      sections.marco_normativo ||
      sections.analisis_situacion ||
      sections.conclusion_recomendacion);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold text-slate-500">
        <div className="flex items-center gap-2">
          <Scale className="h-3.5 w-3.5 text-amber-700" />
          <span>Dictamen Analítico de {response.bot_name}</span>
        </div>
        {response.retrieval_query && (
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-200/80 px-2.5 py-0.5 text-[11px] font-normal text-slate-700">
            <CornerDownRight className="h-3 w-3 text-slate-500" />
            Seguimiento contextualizado con turno previo
          </span>
        )}
      </div>

      {hasStructuredContent && sections ? (
        <div className="grid gap-3">
          {SECTION_CONFIG.map((cfg, index) => {
            const content = sections[cfg.key];
            if (!content) return null;
            const Icon = cfg.icon;
            return (
              <div
                key={cfg.key}
                style={{ animationDelay: `${index * 350}ms` }}
                className={`animate-fade-in-up rounded-xl border border-slate-200 border-l-4 ${cfg.borderColor} bg-white p-4 shadow-sm`}
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${cfg.badgeClass}`}
                    >
                      {cfg.number}
                    </span>
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">
                        {cfg.title}
                      </h3>
                      <p className="text-[11px] text-slate-500">{cfg.subtitle}</p>
                    </div>
                  </div>
                  <Icon className="h-4 w-4 text-slate-400" />
                </div>
                <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed">
                  <ReactMarkdown>{content}</ReactMarkdown>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-800 shadow-sm">
          <div className="prose prose-sm max-w-none leading-relaxed">
            <ReactMarkdown>{response.answer}</ReactMarkdown>
          </div>
        </div>
      )}

      <div
        style={{ animationDelay: "1400ms" }}
        className="animate-fade-in-up"
      >
        <SourceCitations
          sources={response.sources}
          maxScore={response.max_relevance_score}
          thresholdUsed={response.threshold_used}
        />
      </div>

      {response.related_cases && response.related_cases.length > 0 && (
        <div
          style={{ animationDelay: "1600ms" }}
          className="animate-fade-in-up rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm"
        >
          <div className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-slate-700">
            <Sparkles className="h-3.5 w-3.5 text-amber-600" />
            Casos y Situaciones Relacionadas en el Corpus
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            {response.related_cases.map((rc) => (
              <button
                key={rc.id}
                type="button"
                onClick={() => onAsk?.(rc.prompt)}
                className="rounded-lg border border-slate-200 bg-slate-50/70 p-2.5 text-left text-xs transition hover:border-amber-400 hover:bg-amber-50/40"
              >
                <span className="inline-block rounded bg-amber-100/80 px-1.5 py-0.5 text-[10px] font-semibold text-amber-900">
                  {rc.category}
                </span>
                <p className="mt-1 font-semibold text-slate-900">{rc.title}</p>
                <p className="mt-0.5 line-clamp-2 text-[11px] text-slate-600">
                  {rc.summary}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
