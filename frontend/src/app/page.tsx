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
  const [error, setError] = useState<string | null>(null);
  const activeTab = tabs.find((item) => item.id === tab)!;

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api.listExperts({ signal: controller.signal }), api.interviewGuide(controller.signal)])
      .then(([sourceExperts, guide]) => {
        setExperts(sourceExperts);
        setQuestionCount(guide.questions.length);
      })
      .catch((reason) => {
        if (!isAbortError(reason)) setError(String(reason));
      });
    return () => controller.abort();
  }, []);

  const markets = experts.map((expert) => expert.market).join(" · ");

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

        <div className="px-6 py-8 sm:px-9 lg:px-10 lg:py-10">
          <section className="flex justify-end border-b border-slate-200/80 pb-8">
            <div className="hidden">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[#d9e8e5] bg-[#eff7f5] px-3 py-1 text-xs font-semibold tracking-wide text-[#2c6b65]">
                EUROPEAN MEDTECH RESEARCH · 2026
              </div>
              <h1 className="max-w-3xl text-3xl font-semibold tracking-[-0.045em] text-slate-900 sm:text-4xl lg:text-[2.75rem] lg:leading-[1.06]">
                Robotic surgery, <span className="text-[#43827a]">seen through</span> the people who
                buy and use it.
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
                A decision-ready reading of three expert calls across France, Germany, and the UK.
                Every finding stays connected to the exact words and moment that support it.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
              {[
                [String(experts.length || "—"), "expert calls"],
                [String(questionCount ?? "—"), "guide questions"],
                ["100%", "traceable"],
              ].map(([value, label]) => (
                <div key={label} className="rounded-xl bg-slate-50 px-3 py-3 text-center">
                  <p className="text-lg font-semibold tracking-tight text-slate-900">{value}</p>
                  <p className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
                    {label}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {error && (
            <div className="mt-6 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
              The research service is unavailable. Please check that the backend is running.{" "}
              <span className="text-red-500">{error}</span>
            </div>
          )}

          <nav
            aria-label="Research views"
            className="mt-7 grid gap-2 rounded-2xl bg-slate-100/80 p-2 sm:grid-cols-2 lg:grid-cols-4"
          >
            {tabs.map((item, index) => (
              <button
                key={item.id}
                onClick={() => setTab(item.id)}
                className={`group rounded-xl px-4 py-3 text-left transition ${tab === item.id ? "bg-white shadow-sm ring-1 ring-slate-200/80" : "hover:bg-white/70"}`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`grid h-6 w-6 place-items-center rounded-md text-xs font-semibold ${tab === item.id ? "bg-[#19243a] text-white" : "bg-slate-200 text-slate-600"}`}
                  >
                    0{index + 1}
                  </span>
                  <span
                    className={`text-sm font-semibold ${tab === item.id ? "text-slate-900" : "text-slate-600"}`}
                  >
                    {item.label}
                  </span>
                </div>
                <p className="mt-1.5 pl-8 text-xs leading-4 text-slate-500">{item.description}</p>
              </button>
            ))}
          </nav>

          <main className="mt-8">
            <div className="mb-5 flex items-end justify-between gap-4">
              <div>
                <p className="text-[11px] font-bold tracking-[0.14em] text-[#43827a]">
                  {activeTab.eyebrow.toUpperCase()}
                </p>
                <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-900">
                  {activeTab.label}
                </h2>
              </div>
              <p className="hidden text-right text-xs text-slate-500 sm:block">
                Grounded answers · exact transcript citations
              </p>
            </div>
            <ErrorBoundary key={tab}>
              {tab === "qa" && experts.length > 0 && <ExpertQAPanel experts={experts} />}
              {tab === "qa" && experts.length === 0 && !error && (
                <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
                  Loading source profiles…
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
