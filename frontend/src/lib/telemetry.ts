type ClientEvent = {
  event: "ui_error" | "unhandled_rejection";
  errorName: string;
  path: string;
  timestamp: string;
};

const endpoint = process.env.NEXT_PUBLIC_FRONTEND_OBSERVABILITY_ENDPOINT;

/**
 * Sends a deliberately minimal client failure signal when an observability
 * endpoint is configured. It never includes session tokens, emails, query
 * text, transcript content, or raw error messages.
 */
export function reportClientFailure(event: ClientEvent["event"], reason: unknown): void {
  if (!endpoint || typeof window === "undefined") return;

  const errorName = reason instanceof Error ? reason.name : "UnknownError";
  const payload: ClientEvent = {
    event,
    errorName,
    path: window.location.pathname,
    timestamp: new Date().toISOString(),
  };
  const body = JSON.stringify(payload);

  if (navigator.sendBeacon) {
    navigator.sendBeacon(endpoint, new Blob([body], { type: "application/json" }));
    return;
  }
  void fetch(endpoint, {
    method: "POST",
    body,
    headers: { "Content-Type": "application/json" },
    keepalive: true,
  }).catch(() => undefined);
}
