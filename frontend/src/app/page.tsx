"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Header } from "@/components/Header";
import { KnowledgeBaseSidebar } from "@/components/KnowledgeBaseSidebar";
import { ChatInterface } from "@/components/ChatInterface";
import { fetchHealth, fetchSources, triggerIngest } from "@/lib/api";
import { HealthResponse, KnowledgeSourceInfo } from "@/types/chat";

export default function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [sources, setSources] = useState<KnowledgeSourceInfo[]>([]);
  const [threshold, setThreshold] = useState<number>(0.45);
  const [selectedPrompt, setSelectedPrompt] = useState<string>("");
  const [isIngesting, setIsIngesting] = useState<boolean>(false);
  const [ingestBanner, setIngestBanner] = useState<string | null>(null);

  const loadMetadata = useCallback(async () => {
    try {
      const [h, s] = await Promise.all([fetchHealth(), fetchSources()]);
      setHealth(h);
      setSources(s.sources);
      setThreshold(h.score_threshold);
    } catch {
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    loadMetadata();
  }, [loadMetadata]);

  async function handleIngest() {
    setIsIngesting(true);
    setIngestBanner(null);
    try {
      const res = await triggerIngest(true);
      setIngestBanner(
        `Ingesta completada: ${res.files_processed} PDFs, ${res.pages_loaded} páginas y ${res.chunks_indexed} chunks indexados en ChromaDB.`
      );
      await loadMetadata();
    } catch (err) {
      setIngestBanner(
        err instanceof Error
          ? `Error en la ingesta: ${err.message}`
          : "Error al re-indexar la base documental."
      );
    } finally {
      setIsIngesting(false);
    }
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50">
      <Header
        health={health}
        isIngesting={isIngesting}
        onIngest={handleIngest}
        threshold={threshold}
        onThresholdChange={setThreshold}
      />

      {ingestBanner && (
        <div className="border-b border-emerald-200 bg-emerald-50 px-6 py-2 text-xs font-medium text-emerald-900">
          {ingestBanner}
        </div>
      )}

      <main className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="hidden lg:block lg:h-full">
          <KnowledgeBaseSidebar
            sources={sources}
            onSelectPrompt={(prompt) => setSelectedPrompt(prompt)}
          />
        </div>
        <ChatInterface
          selectedPrompt={selectedPrompt}
          onPromptConsumed={() => setSelectedPrompt("")}
          threshold={threshold}
        />
      </main>
    </div>
  );
}
