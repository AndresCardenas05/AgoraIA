"use client";

import React, { useState } from "react";
import { BookMarked, ChevronDown, ChevronUp, FileCheck2 } from "lucide-react";
import { SourceCitation } from "@/types/chat";

interface SourceCitationsProps {
  sources: SourceCitation[];
  maxScore: number;
  thresholdUsed: number;
}

export function SourceCitations({
  sources,
  maxScore,
  thresholdUsed,
}: SourceCitationsProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3.5">
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-slate-700">
          <BookMarked className="h-4 w-4 text-emerald-700" />
          Fuentes Verificadas Citadas ({sources.length})
        </div>
        <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-medium text-emerald-800">
          Similitud máx: {(maxScore * 100).toFixed(0)}% (umbral {(thresholdUsed * 100).toFixed(0)}%)
        </span>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {sources.map((src, idx) => {
          const isOpen = expandedIndex === idx;
          return (
            <div
              key={`${src.source_file}-${src.page ?? 0}-${idx}`}
              className="rounded-lg border border-slate-200 bg-white p-2.5 text-xs shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 font-semibold text-slate-900">
                    <FileCheck2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                    <span className="truncate">{src.document_title}</span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-700">
                      {src.category}
                    </span>
                    {src.page && <span>Pág. {src.page}</span>}
                    {src.article_hint && (
                      <span className="rounded bg-amber-50 px-1.5 py-0.5 font-medium text-amber-800">
                        {src.article_hint}
                      </span>
                    )}
                  </div>
                </div>
                <span className="shrink-0 rounded-md bg-emerald-50 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-emerald-700">
                  {(src.relevance_score * 100).toFixed(0)}%
                </span>
              </div>

              <button
                type="button"
                onClick={() => setExpandedIndex(isOpen ? null : idx)}
                className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-slate-600 hover:text-slate-900"
              >
                {isOpen ? (
                  <>
                    Ocultar extracto <ChevronUp className="h-3 w-3" />
                  </>
                ) : (
                  <>
                    Ver extracto recuperado <ChevronDown className="h-3 w-3" />
                  </>
                )}
              </button>

              {isOpen && (
                <blockquote className="mt-2 rounded border-l-2 border-amber-500 bg-slate-50 p-2 text-[11px] italic leading-relaxed text-slate-700">
                  &ldquo;{src.excerpt}&rdquo;
                </blockquote>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
