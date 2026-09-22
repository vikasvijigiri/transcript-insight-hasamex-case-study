"use client";

import { useEffect, useState } from "react";
import { api, ExpertMeta, ExpertQAResponse } from "@/lib/api";
import CitationChips from "./CitationChips";

export default function ExpertQAPanel({ experts }: { experts: ExpertMeta[] }) {
  const [activeId, setActiveId] = useState(experts[0]?.id ?? "");
  const [data, setData] = useState<ExpertQAResponse | null>(null);
  const [error, setError] = useState<{ id: string; message: string } | null>(null);

  useEffect(() => {
    if (!activeId) return;
    api
      .expertQA(activeId)
      .then(setData)
      .catch((e) => setError({ id: activeId, message: String(e) }));
  }, [activeId]);

  // Derived from data/activeId rather than a separate loading flag, so the effect
  // never resets state synchronously on id change (avoids stale-data flashes and
  // cascading renders — see react-hooks/set-state-in-effect).
  const currentError = error?.id === activeId ? error.message : null;
  const loading = activeId !== "" && !currentError && data?.expert_id !== activeId;

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2">
        {experts.map((e) => (
          <button
            key={e.id}
            onClick={() => setActiveId(e.id)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
              activeId === e.id
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300"
            }`}
          >
            {e.name} · {e.market}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-zinc-500">Analysing transcript with Claude…</p>}
      {currentError && <p className="text-sm text-red-600">{currentError}</p>}

      {data && data.expert_id === activeId && (
        <div className="flex flex-col gap-4">
          <div className="text-sm text-zinc-500">
            {data.role} — {data.market}
          </div>
          {data.answers.map((a, i) => (
            <div key={i} className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <p className="text-sm font-semibold text-zinc-500">
                Q{i + 1}. {a.question}
              </p>
              <p className="mt-2 text-base text-zinc-900 dark:text-zinc-100">{a.answer}</p>
              <CitationChips citations={a.citations} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
