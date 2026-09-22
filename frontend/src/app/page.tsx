"use client";

import { useEffect, useState } from "react";
import { api, ExpertMeta } from "@/lib/api";
import ExpertQAPanel from "@/components/ExpertQAPanel";
import ThemesPanel from "@/components/ThemesPanel";
import ChatPanel from "@/components/ChatPanel";
import { ErrorBoundary } from "@/components/ErrorBoundary";

type Tab = "qa" | "themes" | "chat";

export default function Home() {
  const [tab, setTab] = useState<Tab>("qa");
  const [experts, setExperts] = useState<ExpertMeta[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listExperts()
      .then(setExperts)
      .catch((e) => setError(String(e)));
  }, []);

  const tabs: { id: Tab; label: string }[] = [
    { id: "qa", label: "Expert Q&A" },
    { id: "themes", label: "Themes & Disagreements" },
    { id: "chat", label: "Ask a Question" },
  ];

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black">
      <div className="mx-auto max-w-4xl px-6 py-10">
        <header className="mb-8">
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
            Transcript Insight — Robotic Surgery Market
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            3 expert-call transcripts · every answer below is grounded in a citation with an exact
            quote and timestamp from the source transcript.
          </p>
        </header>

        {error && (
          <p className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
            Could not reach the backend at NEXT_PUBLIC_API_BASE — is it running? ({error})
          </p>
        )}

        <nav className="mb-6 flex gap-1 border-b border-zinc-200 dark:border-zinc-800">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 text-sm font-medium ${
                tab === t.id
                  ? "border-b-2 border-zinc-900 text-zinc-900 dark:border-zinc-100 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <main>
          <ErrorBoundary key={tab}>
            {tab === "qa" && experts.length > 0 && <ExpertQAPanel experts={experts} />}
            {tab === "themes" && <ThemesPanel />}
            {tab === "chat" && <ChatPanel />}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
