"use client";

import React, { useState } from "react";
import {
  BookOpen,
  FileText,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Briefcase,
} from "lucide-react";
import { KnowledgeSourceInfo } from "@/types/chat";

interface KnowledgeBaseSidebarProps {
  sources: KnowledgeSourceInfo[];
  onSelectPrompt: (prompt: string) => void;
}

type PromptTab = "dilemas" | "casos" | "conceptos";

const DILEMMA_PROMPTS: { title: string; prompt: string }[] = [
  {
    title: "Clonación de voz con IA sin aviso",
    prompt:
      "Un medio de noticias utiliza IA generativa para clonar la voz de un locutor fallecido y recrear un audio de un hecho policial reciente sin aclararlo a la audiencia. ¿Qué dilema ético y marco legal argentino aplica?",
  },
  {
    title: "Secreto de fuentes vs. datos sensibles",
    prompt:
      "Un periodista recibe una filtración con historiales clínicos de funcionarios públicos (datos sensibles) y la justicia le exige revelar quién entregó la base de datos. ¿Cómo actúan la Constitución Nacional y la Ley 25.326?",
  },
  {
    title: "Scraping de noticias y motores generativos",
    prompt:
      "Un buscador con respuestas generativas (zero-click) resume notas de investigación de un diario argentino sin pedir autorización ni pagar compensación, reduciendo el tráfico SEO. ¿Qué establecen la Ley 11.723 y el Informe ADEPA 2026?",
  },
  {
    title: "Cobertura de menores y horario apto",
    prompt:
      "En un programa periodístico transmitido a las 15:00 hs se difunden imágenes de un menor involucrado en un conflicto policial sin proteger su identidad. ¿Qué establece la Ley 26.522 al respecto?",
  },
];

const CASE_PROMPTS: { title: string; prompt: string }[] = [
  {
    title: "Caso Perfil vs. OpenAI y Microsoft",
    prompt:
      "¿Qué plantea el caso de la demanda de Editorial Perfil contra OpenAI y Microsoft según el Informe ADEPA 2026?",
  },
  {
    title: "Dilema Bloquear vs. Ser Encontrado",
    prompt:
      "¿Cuál es el dilema entre bloquear el scraping con robots.txt y ser encontrado por los buscadores según ADEPA 2026?",
  },
  {
    title: "Brecha de Gobernanza en Redacciones",
    prompt:
      "¿Qué brecha de gobernanza de la IA detecta el Informe ADEPA 2026 entre medios y periodistas?",
  },
  {
    title: "Marco Comparado (Canadá, Australia, UE)",
    prompt:
      "¿Qué marcos regulatorios de otros países menciona el Informe ADEPA 2026 sobre compensación a los medios por el uso de IA?",
  },
];

const CONCEPT_PROMPTS: { title: string; prompt: string }[] = [
  {
    title: "Secreto de fuentes (Art. 43 CN)",
    prompt:
      "¿Qué protege el Art. 43 de la Constitución respecto del secreto de las fuentes periodísticas?",
  },
  {
    title: "Datos sensibles (Ley 25.326)",
    prompt: "¿Qué se considera dato sensible según la Ley 25.326?",
  },
  {
    title: "Derecho de cita (Ley 11.723)",
    prompt: "¿Cuántas palabras se pueden citar de una obra según la Ley 11.723?",
  },
  {
    title: "Principio Human-in-the-loop (ADEPA)",
    prompt: "¿Qué significa human-in-the-loop en el Informe ADEPA 2026?",
  },
];

export function KnowledgeBaseSidebar({
  sources,
  onSelectPrompt,
}: KnowledgeBaseSidebarProps) {
  const [tab, setTab] = useState<PromptTab>("dilemas");

  const activeList =
    tab === "dilemas"
      ? DILEMMA_PROMPTS
      : tab === "casos"
        ? CASE_PROMPTS
        : CONCEPT_PROMPTS;

  return (
    <aside className="flex h-full w-full flex-col gap-5 overflow-y-auto border-r border-slate-200 bg-slate-50/70 p-4 lg:w-80 xl:w-96">
      <section>
        <div className="mb-2.5 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-600">
          <Sparkles className="h-4 w-4 text-amber-600" />
          Explorar Consultas Guiadas
        </div>

        <div className="mb-3 grid grid-cols-3 gap-1 rounded-lg bg-slate-200/80 p-1 text-[11px] font-semibold">
          <button
            type="button"
            onClick={() => setTab("dilemas")}
            className={`flex items-center justify-center gap-1 rounded-md py-1.5 transition ${
              tab === "dilemas"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Sparkles className="h-3 w-3 text-amber-600" />
            Dilemas
          </button>
          <button
            type="button"
            onClick={() => setTab("casos")}
            className={`flex items-center justify-center gap-1 rounded-md py-1.5 transition ${
              tab === "casos"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Briefcase className="h-3 w-3 text-sky-700" />
            Casos
          </button>
          <button
            type="button"
            onClick={() => setTab("conceptos")}
            className={`flex items-center justify-center gap-1 rounded-md py-1.5 transition ${
              tab === "conceptos"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <HelpCircle className="h-3 w-3 text-emerald-700" />
            Conceptos
          </button>
        </div>

        <div className="space-y-2">
          {activeList.map((item) => (
            <button
              key={item.title}
              type="button"
              onClick={() => onSelectPrompt(item.prompt)}
              className="w-full rounded-xl border border-slate-200 bg-white p-3 text-left transition hover:border-amber-400 hover:shadow-sm"
            >
              <p className="text-xs font-semibold text-slate-900">{item.title}</p>
              <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-slate-500">
                {item.prompt}
              </p>
            </button>
          ))}
        </div>
      </section>

      <section className="border-t border-slate-200 pt-4">
        <div className="mb-2.5 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-600">
          <BookOpen className="h-4 w-4 text-slate-700" />
          Base de Conocimiento ({sources.length})
        </div>
        <div className="space-y-2">
          {sources.map((src) => (
            <div
              key={src.filename}
              className="rounded-xl border border-slate-200 bg-white p-3 text-xs"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-1.5 font-semibold text-slate-900">
                  <FileText className="h-3.5 w-3.5 shrink-0 text-amber-700" />
                  <span>{src.title}</span>
                </div>
                {src.exists_on_disk ? (
                  <CheckCircle2
                    className="h-4 w-4 shrink-0 text-emerald-600"
                    aria-label="PDF disponible"
                  />
                ) : (
                  <AlertCircle
                    className="h-4 w-4 shrink-0 text-rose-500"
                    aria-label="PDF faltante"
                  />
                )}
              </div>
              <span className="mt-1.5 inline-block rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                {src.category}
              </span>
              <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">
                {src.description}
              </p>
            </div>
          ))}
        </div>
      </section>
    </aside>
  );
}
