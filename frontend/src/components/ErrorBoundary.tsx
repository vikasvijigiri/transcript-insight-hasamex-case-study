"use client";

import { Component, ReactNode } from "react";

import { reportClientFailure } from "@/lib/telemetry";

type Props = { children: ReactNode };
type State = { error: Error | null };

/**
 * Catches render-time exceptions in a panel (e.g. a malformed API response
 * shape) so one broken tab shows an inline error instead of blanking the
 * whole page. Network/fetch errors are handled separately per-panel (see
 * the `error` state in ExpertQAPanel/ThemesPanel/ChatPanel) — this is the
 * backstop for everything else.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    console.error("Unhandled UI error:", error, info.componentStack);
    reportClientFailure("ui_error", error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <p className="font-semibold">Something went wrong rendering this panel.</p>
          <p className="mt-1 text-red-600">{this.state.error.message}</p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-2 rounded bg-red-600 px-3 py-1 text-xs font-medium text-white"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
