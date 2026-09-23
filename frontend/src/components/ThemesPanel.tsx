"use client";

import { useEffect, useState } from "react";
import { api, ThemesResponse } from "@/lib/api";
import CitationChips from "./CitationChips";

export default function ThemesPanel() {
  const [data, setData] = useState<ThemesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .themes()
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
        Synthesising the three source conversations…
      </div>
    );
  if (error) return <p className="rounded-xl bg-red-50 p-4 text-sm text-red-600">{error}</p>;
  if (!data) return null;

  return (
    <div className="space-y-5">
      <p className="text-xs font-semibold text-[#39766f]">
        {data.context_mode === "full_transcript_fallback"
          ? "Full transcript fallback · selected by RAG policy"
          : "Retrieved RAG evidence"}
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="overflow-hidden rounded-2xl border border-[#cfe5de] bg-white shadow-sm">
          <div className="border-b border-[#dcece7] bg-[#eff7f5] px-5 py-4">
            <p className="text-[11px] font-bold tracking-[0.14em] text-[#39766f]">
              WHERE THEY ALIGN
            </p>
            <h3 className="mt-1 text-base font-semibold text-slate-900">Shared market signals</h3>
          </div>
          <pre className="whitespace-pre-wrap px-5 py-5 font-sans text-sm leading-6 text-slate-600">
            {data.common_themes}
          </pre>
        </section>
        <section className="overflow-hidden rounded-2xl border border-[#f0dfc2] bg-white shadow-sm">
          <div className="border-b border-[#f3e6cf] bg-[#fff8ed] px-5 py-4">
            <p className="text-[11px] font-bold tracking-[0.14em] text-[#a16b25]">
              WHERE CONTEXT CHANGES THE ANSWER
            </p>
            <h3 className="mt-1 text-base font-semibold text-slate-900">Useful differences</h3>
          </div>
          <pre className="whitespace-pre-wrap px-5 py-5 font-sans text-sm leading-6 text-slate-600">
            {data.disagreements}
          </pre>
        </section>
      </div>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-1 border-b border-slate-100 pb-4">
          <p className="text-[11px] font-bold tracking-[0.14em] text-slate-500">AUDIT TRAIL</p>
          <h3 className="text-base font-semibold text-slate-900">
            Read the evidence behind the synthesis
          </h3>
          <p className="text-xs leading-5 text-slate-500">
            Quotes are kept separate from the interpretation so a reader can judge the claim for
            themselves.
          </p>
        </div>
        <CitationChips citations={data.citations} />
      </section>
    </div>
  );
}
