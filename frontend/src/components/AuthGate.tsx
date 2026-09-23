"use client";

import { type ReactNode, useEffect, useState } from "react";

import { googleAuthorizationUrl, supabase } from "@/lib/supabase";

/** Prevents protected API views from rendering before a configured session exists. */
export default function AuthGate({ children }: { children: ReactNode }) {
  const [signedIn, setSignedIn] = useState(!supabase);
  const [error, setError] = useState<string | null>(null);
  // With no explicit redirect URL, Supabase uses the configured Site URL.
  // This avoids hard-coding localhost into a production OAuth flow.
  const fallbackUrl = googleAuthorizationUrl();

  useEffect(() => {
    if (!supabase) return;
    let mounted = true;
    void supabase.auth
      .getSession()
      .then(({ data }) => {
        if (mounted) setSignedIn(Boolean(data.session));
      })
      .catch(() => {
        if (mounted) setError("Unable to contact Supabase. Check the project URL and publishable key.");
      });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSignedIn(Boolean(session));
    });
    return () => {
      mounted = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  if (signedIn) return <>{children}</>;

  return (
    <main className="grid min-h-screen place-items-center p-4 sm:p-6">
      <section className="grid w-full max-w-5xl overflow-hidden rounded-[28px] border border-white/80 bg-[#fbfcfa]/95 shadow-[0_24px_80px_-38px_rgba(25,36,58,0.5)] backdrop-blur lg:grid-cols-[1.2fr_0.8fr]">
        <div className="relative overflow-hidden bg-[#19243a] px-7 py-10 text-white sm:px-12 sm:py-14">
          <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-emerald-400/10 blur-3xl" />
          <div className="relative">
            <div className="mb-12 flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-white text-lg font-bold text-[#19243a] shadow-lg shadow-slate-950/20">H</div>
              <div>
                <p className="text-sm font-semibold">Hasamex</p>
                <p className="text-xs text-slate-300">Evidence workspace</p>
              </div>
            </div>
            <p className="inline-flex rounded-full border border-emerald-200/20 bg-emerald-300/10 px-3 py-1 text-[11px] font-bold tracking-[0.12em] text-emerald-200">
              EUROPEAN MEDTECH RESEARCH &middot; 2026
            </p>
            <h1 className="mt-5 max-w-xl text-3xl font-semibold tracking-[-0.045em] sm:text-4xl sm:leading-[1.08]">
              Robotic surgery, <span className="text-emerald-300">seen through</span> the people who buy and use it.
            </h1>
            <p className="mt-5 max-w-xl text-sm leading-6 text-slate-300 sm:text-base">
              A decision-ready reading of three expert calls across France, Germany, and the UK. Every finding stays connected to the exact words and moment that support it.
            </p>
            <div className="mt-10 flex flex-wrap gap-2 text-xs font-medium text-slate-200">
              <span className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">Exact transcript citations</span>
              <span className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">Expert-led insight</span>
            </div>
          </div>
        </div>

        <div className="flex items-center px-7 py-10 sm:px-12 sm:py-14">
          <div className="w-full">
            <p className="text-sm font-semibold text-slate-900">Welcome to your evidence workspace</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">Sign in with your organization account to access protected research, source transcripts, and citations.</p>
            {error && <p className="mt-5 rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-800">{error}</p>}
            {fallbackUrl && (
              <a
                className="mt-7 flex w-full items-center justify-center gap-2 rounded-xl bg-[#19243a] px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-700 focus:outline-none focus:ring-4 focus:ring-slate-300"
                href={fallbackUrl}
              >
                <span className="grid h-5 w-5 place-items-center rounded-full bg-white text-[11px] font-bold text-[#4285f4]">G</span>
                Continue with Google
              </a>
            )}
            {fallbackUrl && <p className="mt-4 text-center text-xs text-slate-500">You will be redirected securely through Supabase.</p>}
          </div>
        </div>
      </section>
    </main>
  );
}
