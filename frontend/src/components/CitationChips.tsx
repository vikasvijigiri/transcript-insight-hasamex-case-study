"use client";

import { useEffect, useRef, useState } from "react";
import { api, Citation, TranscriptResponse } from "@/lib/api";
import { isAbortError } from "@/lib/requests";

export function TranscriptDrawer({ citation, onClose }: { citation: Citation; onClose: () => void }) {
  const [transcript, setTranscript] = useState<TranscriptResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    api
      .transcript(citation.expert_id, controller.signal)
      .then(setTranscript)
      .catch((reason) => {
        if (!isAbortError(reason)) setError(String(reason));
      });
    return () => controller.abort();
  }, [citation.expert_id]);

  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not(:disabled), [href], input:not(:disabled), [tabindex]:not([tabindex="-1"])',
      );
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  const parts = transcript?.raw_text.split(citation.quote) ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-end bg-slate-950/35 p-3 backdrop-blur-[2px] sm:items-center sm:justify-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="transcript-title"
    >
      <div ref={dialogRef} className="max-h-[86vh] w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-200 px-5 py-4 sm:px-6">
          <div>
            <p className="text-[10px] font-bold tracking-[0.14em] text-[#43827a]">
              ORIGINAL CALL RECORD
            </p>
            <h3 id="transcript-title" className="mt-1 text-base font-semibold text-slate-900">
              {citation.expert_name} · {citation.timestamp}
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              The highlighted passage is the exact text used to support this finding.
            </p>
          </div>
          <button
            ref={closeRef}
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg text-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
            aria-label="Close transcript"
          >
            ×
          </button>
        </div>
        <div className="max-h-[calc(86vh-105px)] overflow-y-auto px-5 py-5 sm:px-6">
          {!transcript && !error && (
            <p className="text-sm text-slate-500">Opening source record…</p>
          )}
          {error && (
            <p className="rounded-xl bg-red-50 p-3 text-sm text-red-600">
              Unable to open this source record: {error}
            </p>
          )}
          {transcript && (
            <pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-slate-600">
              {parts.length > 1
                ? parts.map((part, index) => (
                    <span key={index}>
                      {part}
                      {index < parts.length - 1 && (
                        <mark className="rounded bg-[#cbe9e2] px-0.5 font-medium text-slate-800 ring-2 ring-[#a7d5cc]">
                          {citation.quote}
                        </mark>
                      )}
                    </span>
                  ))
                : transcript.raw_text}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CitationChips({
  citations,
  onCitationSelect,
}: {
  citations: Citation[];
  onCitationSelect?: (citation: Citation) => void;
}) {
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  if (!citations?.length)
    return (
      <p className="mt-4 text-xs italic text-amber-700">
        No direct quote found — treat this finding with caution.
      </p>
    );

  return (
    <>
      <div className="mt-4 space-y-2 border-t border-slate-100 pt-4">
        <p className="text-[10px] font-bold tracking-[0.14em] text-slate-400">SOURCE EVIDENCE</p>
        {citations.map((citation, index) => (
          <blockquote
            key={index}
            className="rounded-xl border border-[#dce8e5] bg-[#f7faf9] px-3.5 py-3 text-sm leading-5 text-slate-600"
          >
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="rounded bg-[#d8ebe7] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#286960]">
                  {citation.timestamp}
                </span>
                <span className="text-xs font-semibold text-slate-700">{citation.expert_name}</span>
              </div>
              <button
                onClick={() => {
                  if (onCitationSelect) onCitationSelect(citation);
                  else setSelectedCitation(citation);
                }}
                className="shrink-0 rounded-md border border-[#c7ded9] bg-white px-2 py-1 text-[10px] font-semibold text-[#39766f] transition hover:bg-[#e8f4f1]"
              >
                {onCitationSelect ? "Inspect evidence ↗" : "View in call ↗"}
              </button>
            </div>
            <span className="italic">“{citation.quote}”</span>
          </blockquote>
        ))}
      </div>
      {selectedCitation && (
        <TranscriptDrawer citation={selectedCitation} onClose={() => setSelectedCitation(null)} />
      )}
    </>
  );
}
