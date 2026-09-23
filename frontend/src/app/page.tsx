"use client";

import { useEffect, useState } from "react";
import { api, ExpertMeta } from "@/lib/api";
import ExpertQAPanel from "@/components/ExpertQAPanel";
import ThemesPanel from "@/components/ThemesPanel";
import ChatPanel from "@/components/ChatPanel";
import ObservabilityPanel from "@/components/ObservabilityPanel";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import AuthStatus from "@/components/AuthStatus";
import AuthGate from "@/components/AuthGate";
import ClientTelemetry from "@/components/ClientTelemetry";
import { isAbortError } from "@/lib/requests";

type Tab = "qa" | "themes" | "chat" | "operations";

const tabs: { id: Tab; label: string; eyebrow: string; description: string }[] = [
  {
    id: "qa",
    label: "Expert evidence",
    eyebrow: "Source review",
    description: "Answer the guide, one expert at a time.",
  },
  {
    id: "themes",
    label: "Market synthesis",
    eyebrow: "Cross-market view",
    description: "See consensus and productive tension.",
  },
  {
    id: "chat",
    label: "Ask the corpus",
    eyebrow: "Research assistant",
    description: "Explore all three conversations at once.",
  },
  {
    id: "operations",
    label: "RAG operations",
    eyebrow: "Live observability",
    description: "Watch evidence quality and system activity.",
  },
];

export default function Home() {
  return (
    <>
      <ClientTelemetry />
      <AuthGate>
        <Workspace />
      </AuthGate>
    </>
  );
}

function Workspace() {
  const [tab, setTab] = useState<Tab>("qa");
  const [experts, setExperts] = useState<ExpertMeta[]>([]);
  const [questionCount, setQuestionCount] = useState<number | null>(null);
  const [sourcesLoaded, setSourcesLoaded] = useState(false);
  const [sampleImporting, setSampleImporting] = useState(false);
  const [sampleImportError, setSampleImportError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const activeTab = tabs.find((item) => item.id === tab)!;

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api.listExperts({ signal: controller.signal }), api.interviewGuide(controller.signal)])
      .then(([sourceExperts, guide]) => {
        setExperts(sourceExperts);
        setQuestionCount(guide.questions.length);
        setSourcesLoaded(true);
      })
      .catch((reason) => {
        if (!isAbortError(reason)) setError(String(reason));
        setSourcesLoaded(true);
      });
    return () => controller.abort();
  }, []);

  const markets = experts.map((expert) => expert.market).join(" · ");

  async function importBundledCaseStudy() {
    setSampleImporting(true);
    setSampleImportError(null);
    try {
      await api.importSampleCorpus();
      const sourceExperts = await api.listExperts({ limit: 25 });
      setExperts(sourceExperts);
    } catch (reason) {
      setSampleImportError(String(reason));
    } finally {
      setSampleImporting(false);
    }
  }

  return (
    <div className="min-h-screen px-4 py-4 sm:px-6 sm:py-6 lg:px-8">
      <div className="mx-auto max-w-[1536px] overflow-hidden rounded-[28px] border border-white/80 bg-[#fbfcfa]/90 shadow-[0_20px_70px_-36px_rgba(25,36,58,0.45)] backdrop-blur">
        <header className="border-b border-slate-200/80 px-6 py-5 sm:px-9 lg:px-10">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#19243a] text-lg font-semibold text-white shadow-lg shadow-slate-900/15">
                H
              </div>
              <div>
                <p className="text-sm font-semibold tracking-tight text-slate-900">Hasamex</p>
                <p className="text-xs text-slate-500">Evidence workspace</p>
              </div>
            </div>
            <div className="hidden items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-800 sm:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Citation-first analysis
            </div>
            <AuthStatus />
          </div>
        </header>

        <div className="px-6 py-5 sm:px-9 lg:px-10 lg:py-6">

          {error && (
            <div className="mt-6 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
              The research service is unavailable. Please check that the backend is running.{" "}
              <span className="text-red-500">{error}</span>
            </div>
          )}

          <nav
            aria-label="Research views"
            className="mt-5 flex items-center gap-1 overflow-x-auto border-b border-slate-200/80 pb-px"
          >
            {tabs.map((item, index) => (
              <button
                key={item.id}
                onClick={() => setTab(item.id)}
                className={`group relative shrink-0 px-3 py-3 text-left transition sm:px-4 ${tab === item.id ? "text-slate-900" : "text-slate-500 hover:text-slate-800"}`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`grid h-5 w-5 place-items-center rounded-md text-[10px] font-bold ${tab === item.id ? "bg-[#19243a] text-white" : "bg-slate-200 text-slate-500"}`}
                  >
                    0{index + 1}
                  </span>
                  <span
                    className="text-sm font-semibold"
                  >
                    {item.label}
                  </span>
                </div>
                {tab === item.id && (
                  <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-[#43827a] sm:inset-x-4" />
                )}
              </button>
            ))}
            <div className="ml-auto hidden shrink-0 items-center gap-4 px-3 text-right lg:flex">
              {[
                [String(experts.length || "—"), "calls"],
                [String(questionCount ?? "—"), "questions"],
                ["100%", "traceable"],
              ].map(([value, label]) => (
                <span key={label} className="text-xs text-slate-500">
                  <strong className="mr-1 font-semibold text-slate-800">{value}</strong>
                  {label}
                </span>
              ))}
            </div>
          </nav>

          <main className="mt-6">
            <div className="mb-5 flex items-end justify-between gap-4 border-b border-slate-100 pb-4">
              <div>
                <p className="text-[11px] font-bold tracking-[0.14em] text-[#43827a]">
                  {activeTab.eyebrow.toUpperCase()}
                </p>
                <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-900">
                  {activeTab.label}
                </h2>
              </div>
              <p className="hidden max-w-xs text-right text-xs leading-5 text-slate-500 sm:block">
                {activeTab.description} Grounded answers include exact transcript citations.
              </p>
            </div>
            <ErrorBoundary key={tab}>
              {tab === "qa" && experts.length > 0 && <ExpertQAPanel experts={experts} />}
              {tab === "qa" && experts.length === 0 && !error && (
                <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
                  {sourcesLoaded ? (
                    <div className="max-w-xl">
                      <p className="font-semibold text-slate-800">No expert calls in this workspace yet.</p>
                      <p className="mt-2 leading-6">
                        Import the three bundled case-study calls into your protected workspace. They remain isolated to your account.
                      </p>
                      <button
                        className="mt-4 cursor-pointer rounded-xl bg-[#19243a] px-4 py-2.5 text-xs font-semibold text-white shadow-sm transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={sampleImporting}
                        onClick={() => void importBundledCaseStudy()}
                        type="button"
                      >
                        {sampleImporting ? "Importing 3 calls..." : "Import the 3 case-study calls"}
                      </button>
                      {sampleImportError && <p className="mt-3 text-xs text-red-600">{sampleImportError}</p>}
                    </div>
                  ) : (
                    "Loading source profiles..."
                  )}
                </div>
              )}
              {tab === "themes" && <ThemesPanel />}
              {tab === "chat" && <ChatPanel />}
              {tab === "operations" && <ObservabilityPanel />}
            </ErrorBoundary>
          </main>
        </div>

        <footer className="flex flex-col gap-1 border-t border-slate-200/80 bg-slate-50/70 px-6 py-4 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-9 lg:px-10">
          <span>Built for careful market understanding—not unsupported claims.</span>
          <span className="font-medium text-slate-600">{markets || "Loading markets…"}</span>
        </footer>
      </div>
    </div>
  );
}
