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

  if (loading) return <p className="text-sm text-zinc-500">Synthesising across all 3 transcripts…</p>;
  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!data) return null;

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-emerald-600">
          Common Themes
        </h3>
        <pre className="whitespace-pre-wrap font-sans text-sm text-zinc-800 dark:text-zinc-200">
          {data.common_themes}
        </pre>
      </div>
      <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-amber-600">
          Disagreements
        </h3>
        <pre className="whitespace-pre-wrap font-sans text-sm text-zinc-800 dark:text-zinc-200">
          {data.disagreements}
        </pre>
      </div>
      <div className="md:col-span-2">
        <h3 className="mb-2 text-sm font-semibold text-zinc-500">Supporting quotes</h3>
        <CitationChips citations={data.citations} />
      </div>
    </div>
  );
}
