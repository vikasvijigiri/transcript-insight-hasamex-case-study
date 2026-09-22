"use client";

import { useState } from "react";
import { api, Citation } from "@/lib/api";
import CitationChips from "./CitationChips";

type Turn = { question: string; answer: string; citations: Citation[] };

export default function ChatPanel() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask() {
    const q = question.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.chat(q);
      setTurns((prev) => [...prev, { question: q, answer: res.answer, citations: res.citations }]);
      setQuestion("");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
          placeholder="e.g. Do the experts agree on how important ROI is?"
          className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
        />
        <button
          onClick={ask}
          disabled={loading}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {loading ? "Asking…" : "Ask"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex flex-col gap-4">
        {[...turns].reverse().map((t, i) => (
          <div key={i} className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
            <p className="text-sm font-semibold text-zinc-500">You asked: {t.question}</p>
            <p className="mt-2 text-base text-zinc-900 dark:text-zinc-100">{t.answer}</p>
            <CitationChips citations={t.citations} />
          </div>
        ))}
      </div>
    </div>
  );
}
