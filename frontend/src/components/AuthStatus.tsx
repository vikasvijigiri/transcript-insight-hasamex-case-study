"use client";

import { useEffect, useRef, useState } from "react";
import type { User } from "@supabase/supabase-js";

import { authenticationConfigured, googleAuthorizationUrl, supabase } from "@/lib/supabase";

function displayNameFor(user: User): string {
  const metadata = user.user_metadata;
  const name = metadata.full_name ?? metadata.name ?? metadata.preferred_username;
  return typeof name === "string" && name.trim()
    ? name.trim()
    : (user.email?.split("@")[0] ?? "Researcher");
}

function avatarUrlFor(user: User): string | null {
  const avatarUrl = user.user_metadata.avatar_url ?? user.user_metadata.picture;
  return typeof avatarUrl === "string" && avatarUrl.trim() ? avatarUrl : null;
}

function initialsFor(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "R";
}

export default function AuthStatus() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(authenticationConfigured);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!supabase) return;
    let active = true;

    void supabase.auth
      .getSession()
      .then(({ data }) => {
        if (active) setUser(data.session?.user ?? null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  if (!supabase) {
    return <span className="text-xs text-slate-500">Local demo mode</span>;
  }

  if (loading) return <span className="text-xs text-slate-500">Checking sign-in...</span>;

  if (!user) {
    const signInUrl = googleAuthorizationUrl(window.location.origin);
    return signInUrl ? (
      <a
        className="rounded-xl bg-[#19243a] px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
        href={signInUrl}
      >
        Sign in with Google
      </a>
    ) : null;
  }

  const name = displayNameFor(user);
  const avatarUrl = avatarUrlFor(user);
  const initials = initialsFor(name);

  async function signOut() {
    setMenuOpen(false);
    await supabase?.auth.signOut();
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        aria-expanded={menuOpen}
        aria-haspopup="menu"
        aria-label="Open account menu"
        className="flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white py-1.5 pl-1.5 pr-2.5 text-left shadow-sm transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
        onClick={() => setMenuOpen((open) => !open)}
        type="button"
      >
        {avatarUrl ? (
          // Google identity image hosts vary; this small account avatar is intentionally not optimized.
          // eslint-disable-next-line @next/next/no-img-element
          <img alt="" className="h-7 w-7 rounded-lg object-cover" referrerPolicy="no-referrer" src={avatarUrl} />
        ) : (
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-indigo-600 text-[10px] font-bold text-white">
            {initials}
          </span>
        )}
        <span className="max-w-32 truncate text-xs font-semibold text-slate-700">{name}</span>
        <span aria-hidden="true" className="text-xs text-slate-400">v</span>
      </button>

      {menuOpen ? (
        <div
          aria-label="Account menu"
          className="absolute right-0 z-50 mt-2 w-64 overflow-hidden rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl shadow-slate-900/10"
          role="menu"
        >
          <div className="flex items-center gap-3 rounded-xl px-3 py-3">
            {avatarUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img alt="" className="h-10 w-10 rounded-xl object-cover" referrerPolicy="no-referrer" src={avatarUrl} />
            ) : (
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 text-sm font-bold text-white">
                {initials}
              </span>
            )}
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900">{name}</p>
              <p className="truncate text-xs text-slate-500">{user.email}</p>
            </div>
          </div>
          <div className="my-1 border-t border-slate-100" />
          <button
            className="flex w-full cursor-pointer items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-rose-600 transition hover:bg-rose-50 focus:outline-none focus:ring-2 focus:ring-rose-400"
            onClick={() => void signOut()}
            role="menuitem"
            type="button"
          >
            <span aria-hidden="true">Sign out</span>
            <span className="ml-auto text-xs font-medium text-rose-400">Securely</span>
          </button>
        </div>
      ) : null}
    </div>
  );
}
