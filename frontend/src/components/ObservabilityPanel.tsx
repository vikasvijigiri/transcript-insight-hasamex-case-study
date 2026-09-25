"use client";

import { useEffect, useState } from "react";
import { api, ObservabilitySnapshot } from "@/lib/api";
import { isAbortError } from "@/lib/requests";

const initial: ObservabilitySnapshot = {
  requests: 0,
  retrievals: 0,
  verifiedCitations: 0,
  rejectedCitations: 0,
  llmCalls: 0,
  cacheHits: 0,
  cacheMisses: 0,
};

export default function ObservabilityPanel() {
  const [snapshot, setSnapshot] = useState<ObservabilitySnapshot>(initial);
  const [updatedAt, setUpdatedAt] = useState<string>("Connecting…");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const refresh = () =>
      api
        .observability(controller.signal)
        .then((next) => {
          setSnapshot(next);
          setUpdatedAt(new Intl.DateTimeFormat(undefined, { timeStyle: "medium" }).format());
          setError(null);
        })
        .catch((reason) => {
          if (!isAbortError(reason)) setError("Live operational metrics could not be loaded.");
        });
    refresh();
    const intervalId = window.setInterval(refresh, 5000);
    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, []);

  const cards = [
    [snapshot.requests, "API requests"],
    [snapshot.retrievals, "hybrid retrievals"],
    [snapshot.verifiedCitations, "verified citations"],
    [snapshot.rejectedCitations, "rejected citations"],
    [snapshot.llmCalls, "LLM calls"],
    [snapshot.cacheHits, "cache hits"],
    [snapshot.cacheMisses, "cache misses"],
  ];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-900">Live RAG operations</p>
          <p className="mt-1 text-sm text-slate-500">
            Refreshes every 5 seconds. Only aggregate operational data is shown.
          </p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-800">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> {updatedAt}
        </span>
      </div>
      {error ? (
        <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      ) : (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map(([value, label]) => (
            <div key={String(label)} className="rounded-xl bg-slate-50 px-4 py-4">
              <p className="text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
              <p className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-500">
                {label}
              </p>
            </div>
          ))}
        </div>
      )}
      <p className="mt-5 text-xs text-slate-500">
        This panel is the live local dashboard. Grafana is provisioned for the production Compose
        stack.
        {" · "}
        <a
          className="font-medium text-[#2c6b65] underline underline-offset-2"
          href="http://localhost:8000/metrics"
          target="_blank"
          rel="noreferrer"
        >
          Prometheus metrics
        </a>
      </p>
    </section>
  );
}
