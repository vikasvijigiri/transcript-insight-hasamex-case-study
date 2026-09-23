"use client";

import { type FormEvent, useEffect, useState } from "react";
import { api, Citation, ExpertMeta, ExpertQAResponse, TranscriptResponse } from "@/lib/api";
import { isAbortError } from "@/lib/requests";
import CitationChips from "./CitationChips";

function EvidenceRail({ citation }: { citation: Citation | null }) {
  const [transcript, setTranscript] = useState<TranscriptResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    if (citation)
      api
        .transcript(citation.expert_id, controller.signal)
        .then(setTranscript)
        .catch((reason) => {
          if (!isAbortError(reason)) setError(String(reason));
        });
    return () => controller.abort();
  }, [citation]);

  if (!citation)
    return (
      <aside className="hidden xl:block">
        <div className="sticky top-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-[10px] font-bold tracking-[0.14em] text-slate-400">
            EVIDENCE INSPECTOR
          </p>
          <h3 className="mt-2 text-sm font-semibold text-slate-800">Verify a finding in context</h3>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            Select a citation under any answer. The original passage will open here without moving you away from the analysis.
          </p>
          <ol className="mt-5 space-y-3 border-t border-slate-100 pt-4 text-xs text-slate-600">
            <li className="flex gap-2"><span className="font-semibold text-[#39766f]">01</span><span>Read the synthesized answer.</span></li>
            <li className="flex gap-2"><span className="font-semibold text-[#39766f]">02</span><span>Open its timestamped citation.</span></li>
            <li className="flex gap-2"><span className="font-semibold text-[#39766f]">03</span><span>Review the source passage.</span></li>
          </ol>
        </div>
      </aside>
    );

  const raw = transcript?.raw_text ?? "";
  const start = Math.max(0, raw.indexOf(citation.quote) - 170);
  const end = Math.min(raw.length, raw.indexOf(citation.quote) + citation.quote.length + 210);
  const excerpt = raw.slice(start, end);
  const parts = excerpt.split(citation.quote);

  return (
    <aside className="hidden xl:block">
      <div className="sticky top-5 overflow-hidden rounded-2xl border border-[#cfe5de] bg-white shadow-sm">
        <div className="border-b border-[#dcece7] bg-[#eff7f5] px-5 py-4">
          <p className="text-[10px] font-bold tracking-[0.14em] text-[#39766f]">
            EVIDENCE INSPECTOR
          </p>
          <h3 className="mt-1 text-sm font-semibold text-slate-900">Original call record</h3>
          <p className="mt-1 text-xs text-[#39766f]">
            {citation.expert_name} · {citation.timestamp}
          </p>
        </div>
        <div className="p-5">
          {!transcript && !error && (
            <p className="text-xs text-slate-500">Opening source record…</p>
          )}
          {error && (
            <p className="text-xs leading-5 text-red-600">
              Could not open this source record: {error}
            </p>
          )}
          {transcript && (
            <>
              <pre className="whitespace-pre-wrap font-sans text-xs leading-6 text-slate-600">
                {parts.length > 1
                  ? parts.map((part, index) => (
                      <span key={index}>
                        {part}
                        {index < parts.length - 1 && (
                          <mark className="rounded bg-[#cbe9e2] px-0.5 font-medium text-slate-800">
                            {citation.quote}
                          </mark>
                        )}
                      </span>
                    ))
                  : excerpt}
              </pre>
              {!expanded && (
                <p className="mt-3 text-[11px] italic text-slate-400">
                  Excerpt shown around the cited passage.
                </p>
              )}
              {expanded && (
                <pre className="mt-4 max-h-80 overflow-y-auto whitespace-pre-wrap border-t border-slate-100 pt-4 font-sans text-xs leading-6 text-slate-600">
                  {raw}
                </pre>
              )}
              <button
                onClick={() => setExpanded((value) => !value)}
                className="mt-4 w-full rounded-lg border border-[#c7ded9] px-3 py-2 text-xs font-semibold text-[#39766f] transition hover:bg-[#eff7f5]"
              >
                {expanded ? "Show excerpt" : "Read full transcript"}
              </button>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}

export default function ExpertQAPanel({ experts }: { experts: ExpertMeta[] }) {
  const [activeId, setActiveId] = useState(experts[0]?.id ?? "");
  const [sourceProfiles, setSourceProfiles] = useState(experts);
  const [sourceQuery, setSourceQuery] = useState("");
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [hasMoreSources, setHasMoreSources] = useState(experts.length === 25);
  const [data, setData] = useState<ExpertQAResponse | null>(null);
  const [error, setError] = useState<{ id: string; message: string } | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    if (activeId) {
      api
        .expertQA(activeId, controller.signal)
        .then(setData)
        .catch((reason) => {
          if (!isAbortError(reason)) setError({ id: activeId, message: String(reason) });
        });
    }
    return () => controller.abort();
  }, [activeId]);

  function selectExpert(id: string) {
    setData(null);
    setError(null);
    setActiveId(id);
  }

  async function searchSources(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSourceLoading(true);
    setSourceError(null);
    try {
      const next = await api.listExperts({ query: sourceQuery.trim(), limit: 25 });
      setSourceProfiles(next);
      setHasMoreSources(next.length === 25);
      selectExpert(next[0]?.id ?? "");
    } catch (reason) {
      setSourceError(String(reason));
    } finally {
      setSourceLoading(false);
    }
  }

  async function loadMoreSources() {
    setSourceLoading(true);
    setSourceError(null);
    try {
      const next = await api.listExperts({
        query: sourceQuery.trim(),
        offset: sourceProfiles.length,
        limit: 25,
      });
      setSourceProfiles((current) => [...current, ...next]);
      setHasMoreSources(next.length === 25);
    } catch (reason) {
      setSourceError(String(reason));
    } finally {
      setSourceLoading(false);
    }
  }

  const currentError = error?.id === activeId ? error.message : null;
  const loading = activeId !== "" && !currentError && data?.expert_id !== activeId;
  const activeExpert = sourceProfiles.find((expert) => expert.id === activeId);
  const nextMarket = activeExpert?.market;
  const displayName =
    data?.expert_name === data?.expert_id
      ? activeExpert?.name ?? data?.expert_name
      : data?.expert_name;

  return (
    <div className="grid gap-6 lg:grid-cols-[248px_minmax(0,1fr)] xl:grid-cols-[248px_minmax(0,1fr)_300px]">
      <aside className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm lg:sticky lg:top-5 lg:self-start">
        <div className="flex items-baseline justify-between px-2 pb-2 pt-1">
          <p className="text-[11px] font-bold tracking-[0.14em] text-slate-500">SOURCE PROFILES</p>
          <span className="text-[11px] font-medium text-slate-400">{sourceProfiles.length}</span>
        </div>
        <form onSubmit={searchSources} className="mb-2 px-1">
          <label className="sr-only" htmlFor="source-search">Search source profiles</label>
          <div className="flex gap-1">
            <input
              id="source-search"
              value={sourceQuery}
              onChange={(event) => setSourceQuery(event.target.value)}
              placeholder="Search calls"
              className="min-w-0 flex-1 rounded-lg border border-slate-200 px-2 py-1.5 text-xs outline-none focus:border-[#43827a] focus:ring-2 focus:ring-[#dceeea]"
            />
            <button className="rounded-lg bg-slate-100 px-2 text-xs font-semibold text-slate-700 hover:bg-slate-200" disabled={sourceLoading}>
              Find
            </button>
          </div>
        </form>
        <div className="flex gap-2 overflow-x-auto lg:max-h-[calc(100vh-19rem)] lg:flex-col lg:overflow-y-auto lg:pr-1">
          {sourceProfiles.map((expert, index) => (
            <button
              key={expert.id}
              onClick={() => selectExpert(expert.id)}
              aria-pressed={activeId === expert.id}
              className={`min-w-[190px] rounded-xl p-3 text-left transition duration-200 lg:min-w-0 ${activeId === expert.id ? "bg-[#19243a] text-white shadow-md shadow-slate-900/15" : "hover:bg-slate-50"}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span
                  className={`grid h-7 w-7 place-items-center rounded-lg text-xs font-bold ${activeId === expert.id ? "bg-white/15 text-white" : "bg-[#e8f1ef] text-[#36766e]"}`}
                >
                  0{index + 1}
                </span>
                <span
                  className={`text-[10px] font-bold tracking-wider ${activeId === expert.id ? "text-[#a9d7cf]" : "text-slate-400"}`}
                >
                  {expert.market.toUpperCase()}
                </span>
              </div>
              <p className="mt-3 text-sm font-semibold">{expert.name}</p>
              <p
                className={`mt-1 text-xs leading-4 ${activeId === expert.id ? "text-slate-300" : "text-slate-500"}`}
              >
                {expert.role}
              </p>
            </button>
          ))}
        </div>
        {sourceProfiles.length === 0 && !sourceLoading && (
          <p className="px-2 py-3 text-xs text-slate-500">No source profiles match this search.</p>
        )}
        {sourceError && <p className="px-2 py-2 text-xs text-red-600">{sourceError}</p>}
        {hasMoreSources && (
          <button
            onClick={loadMoreSources}
            disabled={sourceLoading}
            className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
          >
            {sourceLoading ? "Loading…" : "Load 25 more"}
          </button>
        )}
      </aside>
      <section className="relative min-h-48">
        {loading && (
          <div className="absolute right-0 top-0 z-10 inline-flex items-center gap-2 rounded-full border border-[#d9e8e5] bg-white/95 px-3 py-1.5 text-xs font-medium text-[#39766f] shadow-sm backdrop-blur">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#43827a]" /> Loading{" "}
            {nextMarket} insights
          </div>
        )}
        {currentError && (
          <p className="rounded-xl bg-red-50 p-4 text-sm text-red-600">{currentError}</p>
        )}
        {data && (
          <div
            key={data.expert_id}
            className={`space-y-4 transition-opacity duration-200 motion-reduce:transition-none ${loading ? "opacity-55" : "animate-[fade-in_220ms_ease-out] opacity-100"}`}
          >
            <div className="flex flex-col gap-3 rounded-2xl border border-[#d9e8e5] bg-[#eff7f5] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-900">{displayName}</p>
                <p className="mt-1 text-xs text-[#39766f]">
                  {data.role} · {data.market} market perspective · 6 guide questions
                </p>
              </div>
              <p className="shrink-0 text-xs font-semibold text-[#39766f]">
                {data.context_mode === "full_transcript_fallback"
                  ? "Full transcript fallback · selected by RAG policy"
                  : "Retrieved RAG evidence"}
              </p>
            </div>
            {data.answers.map((answer, index) => (
              <article
                key={index}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_8px_22px_-20px_rgba(25,36,58,0.55)]"
              >
                <div className="flex gap-3">
                  <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-slate-100 text-[11px] font-bold text-slate-500">
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-sm font-semibold leading-5 text-slate-800">
                      {answer.question}
                    </p>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{answer.answer}</p>
                  </div>
                </div>
                <CitationChips
                  citations={answer.citations}
                  onCitationSelect={setSelectedCitation}
                />
              </article>
            ))}
          </div>
        )}
      </section>
      <EvidenceRail
        key={
          selectedCitation
            ? `${selectedCitation.expert_id}:${selectedCitation.timestamp}:${selectedCitation.quote}`
            : "empty"
        }
        citation={selectedCitation}
      />
    </div>
  );
}
