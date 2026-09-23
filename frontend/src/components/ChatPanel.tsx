"use client";

import { useState } from "react";
import { api, Citation } from "@/lib/api";
import CitationChips from "./CitationChips";

type Turn = { question: string; answer: string; citations: Citation[]; contextMode: string };

const suggestions = [
  "Where do experts disagree on ROI?",
  "What would make adoption accelerate?",
  "Compare purchasing timelines by market.",
];

export default function ChatPanel() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask() {
    const q = question.trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.chat(q);
      setTurns((previous) => [
        ...previous,
        { question: q, answer: res.answer, citations: res.citations, contextMode: res.context_mode },
      ]);
      setQuestion("");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="rounded-2xl bg-[#19243a] px-5 py-5 text-white sm:px-6">
        <p className="text-[11px] font-bold tracking-[0.14em] text-[#9fd3ca]">ASK WITH CONTEXT</p>
        <h3 className="mt-1 text-lg font-semibold tracking-tight">
          Search across every expert call.
        </h3>
        <p className="mt-2 max-w-2xl text-sm leading-5 text-slate-300">
          Ask a focused market question. The response is grounded in the supplied transcripts and
          brings its supporting quotes with it.
        </p>
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => setQuestion(suggestion)}
            className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-600 transition hover:border-[#9ccfc6] hover:bg-[#eff7f5] hover:text-[#286960]"
          >
            {suggestion}
          </button>
        ))}
      </div>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="research-question">
          Question
        </label>
        <input
          id="research-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && ask()}
          placeholder="Ask about adoption, economics, training, or purchasing…"
          className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-[#43827a] focus:ring-4 focus:ring-[#dceeea]"
        />
        <button
          onClick={ask}
          disabled={loading || !question.trim()}
          className="rounded-xl bg-[#43827a] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#326e67] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Searching…" : "Ask research"}
        </button>
      </div>
      {error && <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-600">{error}</p>}
      {turns.length === 0 && !loading && (
        <div className="mt-7 border-t border-slate-100 pt-5 text-center">
          <p className="text-sm font-medium text-slate-700">
            Start with a question that helps you make a decision.
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Responses will include source names, timestamps, and exact supporting language.
          </p>
        </div>
      )}
      <div className="mt-5 space-y-4">
        {[...turns].reverse().map((turn, index) => (
          <article key={index} className="rounded-2xl border border-slate-200 bg-[#fbfcfa] p-5">
            <p className="text-[11px] font-bold tracking-[0.12em] text-[#43827a]">YOUR QUESTION</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{turn.question}</p>
            <div className="mt-4 border-l-2 border-[#86bdb4] pl-4">
              <p className="text-[11px] font-bold tracking-[0.12em] text-slate-400">
                EVIDENCE-BASED ANSWER
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-600">{turn.answer}</p>
            </div>
            <p className="mt-3 text-xs font-medium text-[#2c6b65]">
              {turn.contextMode === "full_transcript_fallback"
                ? "Full transcript fallback · selected by RAG policy"
                : "Retrieved RAG evidence"}
            </p>
            <CitationChips citations={turn.citations} />
          </article>
        ))}
      </div>
    </div>
  );
}
