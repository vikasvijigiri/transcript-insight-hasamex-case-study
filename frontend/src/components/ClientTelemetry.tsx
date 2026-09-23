"use client";

import { useEffect } from "react";

import { reportClientFailure } from "@/lib/telemetry";

/** Captures uncaught browser failures without collecting user or research data. */
export default function ClientTelemetry() {
  useEffect(() => {
    const onError = (event: ErrorEvent) => reportClientFailure("ui_error", event.error);
    const onUnhandledRejection = (event: PromiseRejectionEvent) =>
      reportClientFailure("unhandled_rejection", event.reason);

    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandledRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
    };
  }, []);

  return null;
}
