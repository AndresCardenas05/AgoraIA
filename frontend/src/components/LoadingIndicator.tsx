"use client";

import React, { useEffect, useState } from "react";
import { Scale, Check, Loader2 } from "lucide-react";

const STEPS = [
  "Interpretando la consulta",
  "Buscando en la base vectorial de normativa",
  "Evaluando el umbral de relevancia",
  "Redactando el análisis en 4 puntos",
];

const STEP_DURATION_MS = 1100;

export function LoadingIndicator() {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setActiveStep((s) => Math.min(s + 1, STEPS.length - 1));
    }, STEP_DURATION_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <div
      className="flex items-start gap-3 animate-fade-in-up"
      role="status"
      aria-live="polite"
      aria-label="ÁgoraIA está analizando tu consulta"
    >
      <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-800">
        <span className="absolute inset-0 animate-ping rounded-full bg-amber-300/50" />
        <Scale className="relative h-4 w-4" />
      </div>

      <div className="min-w-0 flex-1 rounded-2xl rounded-tl-sm border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          ÁgoraIA está analizando
          <span className="flex items-center gap-1" aria-hidden="true">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-amber-600 [animation-delay:-0.3s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-amber-600 [animation-delay:-0.15s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-amber-600" />
          </span>
        </div>

        <ul className="mt-3 space-y-1.5">
          {STEPS.map((label, idx) => {
            const done = idx < activeStep;
            const current = idx === activeStep;
            return (
              <li
                key={label}
                className={`flex items-center gap-2 text-xs transition-opacity duration-300 ${
                  idx > activeStep ? "opacity-30" : "opacity-100"
                } ${current ? "font-medium text-slate-900" : "text-slate-500"}`}
              >
                {done ? (
                  <Check className="h-3.5 w-3.5 text-emerald-600" />
                ) : current ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-700" />
                ) : (
                  <span className="h-3.5 w-3.5 rounded-full border border-slate-300" />
                )}
                {label}
              </li>
            );
          })}
        </ul>

        <div className="mt-4 space-y-2" aria-hidden="true">
          <div className="h-2.5 w-11/12 animate-pulse rounded bg-slate-100" />
          <div className="h-2.5 w-4/5 animate-pulse rounded bg-slate-100" />
          <div className="h-2.5 w-2/3 animate-pulse rounded bg-slate-100" />
        </div>
      </div>
    </div>
  );
}
