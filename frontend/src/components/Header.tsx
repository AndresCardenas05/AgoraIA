"use client";

import React from "react";
import { Scale, ShieldCheck, Database, RefreshCw, SlidersHorizontal } from "lucide-react";
import { HealthResponse } from "@/types/chat";

interface HeaderProps {
  health: HealthResponse | null;
  isIngesting: boolean;
  onIngest: () => void;
  threshold: number;
  onThresholdChange: (value: number) => void;
}

export function Header({
  health,
  isIngesting,
  onIngest,
  threshold,
  onThresholdChange,
}: HeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white/95 backdrop-blur px-6 py-4 shadow-sm">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-900 text-amber-400 shadow-sm">
            <Scale className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-serif text-xl font-bold tracking-tight text-slate-900">
                ÁgoraIA
              </h1>
              <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
                RAG Ética &amp; Derecho
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Consultor analítico de ética periodística, legislación argentina e IA generativa
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-700">
            <SlidersHorizontal className="h-3.5 w-3.5 text-slate-500" />
            <label htmlFor="threshold-slider" className="font-medium">
              Umbral anti-alucinación:
            </label>
            <input
              id="threshold-slider"
              type="range"
              min="0.20"
              max="0.80"
              step="0.05"
              value={threshold}
              onChange={(e) => onThresholdChange(parseFloat(e.target.value))}
              className="w-20 accent-slate-900"
            />
            <span className="font-mono font-semibold text-slate-900">
              {threshold.toFixed(2)}
            </span>
          </div>

          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs">
            <Database className="h-3.5 w-3.5 text-emerald-600" />
            {health ? (
              <span className="text-slate-700">
                <strong className="text-slate-900">{health.indexed_chunks}</strong> chunks ·{" "}
                <strong className="text-slate-900">{health.pdfs_available}</strong> PDFs
              </span>
            ) : (
              <span className="text-amber-700">Backend desconectado</span>
            )}
          </div>

          <button
            type="button"
            onClick={onIngest}
            disabled={isIngesting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            title="Indexar o re-indexar los PDFs en ChromaDB"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isIngesting ? "animate-spin" : ""}`} />
            {isIngesting ? "Indexando..." : "Re-indexar Corpus"}
          </button>

          <span className="hidden items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 xl:inline-flex">
            <ShieldCheck className="h-3.5 w-3.5" />
            Trazabilidad Estricta
          </span>
        </div>
      </div>
    </header>
  );
}
