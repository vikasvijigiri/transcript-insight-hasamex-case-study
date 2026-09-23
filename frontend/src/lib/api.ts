import { supabase } from "@/lib/supabase";
import { ApiError, withTimeout } from "@/lib/requests";

const configuredApiBase = process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "");
const API_BASE = configuredApiBase ?? (process.env.NODE_ENV === "development" ? "http://localhost:8000" : null);

export type Citation = {
  expert_id: string;
  expert_name: string;
  quote: string;
  timestamp: string;
};

export type ExpertMeta = {
  id: string;
  name: string;
  role: string;
  market: string;
};

export type ExpertAnswer = {
  question: string;
  answer: string;
  citations: Citation[];
};

export type ExpertQAResponse = {
  expert_id: string;
  expert_name: string;
  role: string;
  market: string;
  answers: ExpertAnswer[];
  context_mode: "rag_evidence" | "full_transcript_fallback";
};

export type ThemesResponse = {
  common_themes: string;
  disagreements: string;
  citations: Citation[];
  context_mode: "rag_evidence" | "full_transcript_fallback";
};

export type ChatResponse = {
  answer: string;
  citations: Citation[];
  context_mode: "rag_evidence" | "full_transcript_fallback";
};

export type TranscriptResponse = {
  expert_id: string;
  expert_name: string;
  role: string;
  market: string;
  raw_text: string;
};

export type ObservabilitySnapshot = {
  requests: number;
  retrievals: number;
  verifiedCitations: number;
  rejectedCitations: number;
};

export type SampleCorpusResponse = {
  imported: number;
  already_present: number;
  expert_ids: string[];
};

async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  if (!API_BASE) {
    throw new ApiError("The application is missing NEXT_PUBLIC_API_BASE. Configure the deployed backend URL and rebuild.");
  }
  return withTimeout(async (requestSignal) => {
    const res = await fetch(`${API_BASE}${path}`, { signal: requestSignal, headers: await authHeaders() });
    if (res.status === 401) throw new ApiError("Your session has expired. Please sign in again.", 401);
    if (!res.ok) throw new ApiError("The research service is unavailable. Please try again.", res.status);
    return res.json() as Promise<T>;
  }, signal);
}

async function authHeaders(): Promise<HeadersInit> {
  if (!supabase) return {};
  const { data } = await supabase.auth.getSession();
  return data.session ? { Authorization: `Bearer ${data.session.access_token}` } : {};
}

function metricTotal(metrics: string, metric: string, label?: string): number {
  const rows = metrics.split("\n").filter((row) => row.startsWith(`${metric}{`) || row.startsWith(`${metric} `));
  return rows.reduce((total, row) => {
    if (label && !row.includes(label)) return total;
    const value = Number(row.trim().split(/\s+/).at(-1));
    return total + (Number.isFinite(value) ? value : 0);
  }, 0);
}

export const api = {
  listExperts: (
    options: { query?: string; offset?: number; limit?: number; signal?: AbortSignal } = {},
  ) => {
    const params = new URLSearchParams();
    if (options.query) params.set("query", options.query);
    if (options.offset) params.set("offset", String(options.offset));
    if (options.limit) params.set("limit", String(options.limit));
    const suffix = params.size ? `?${params}` : "";
    return getJSON<ExpertMeta[]>(`/api/experts${suffix}`, options.signal);
  },
  interviewGuide: (signal?: AbortSignal) =>
    getJSON<{ questions: string[] }>("/api/interview-guide", signal),
  importSampleCorpus: () =>
    withTimeout(async (signal) => {
      if (!API_BASE) {
        throw new ApiError("The application is missing NEXT_PUBLIC_API_BASE. Configure the deployed backend URL and rebuild.");
      }
      const response = await fetch(`${API_BASE}/api/projects/Robotics/sample-corpus`, {
        method: "POST",
        signal,
        headers: await authHeaders(),
      });
      if (response.status === 401) throw new ApiError("Your session has expired. Please sign in again.", 401);
      if (!response.ok) throw new ApiError("Unable to import the case-study calls right now.", response.status);
      return response.json() as Promise<SampleCorpusResponse>;
    }),
  expertQA: (expertId: string, signal?: AbortSignal) =>
    getJSON<ExpertQAResponse>(`/api/experts/${expertId}/qa`, signal),
  transcript: (expertId: string, signal?: AbortSignal) =>
    getJSON<TranscriptResponse>(`/api/experts/${expertId}/transcript`, signal),
  themes: (signal?: AbortSignal) => getJSON<ThemesResponse>("/api/themes", signal),
  observability: async (signal?: AbortSignal): Promise<ObservabilitySnapshot> => {
    if (!API_BASE) {
      throw new ApiError("The application is missing NEXT_PUBLIC_API_BASE. Configure the deployed backend URL and rebuild.");
    }
    return withTimeout(async (requestSignal) => {
      const response = await fetch(`${API_BASE}/metrics`, {
        signal: requestSignal,
        headers: await authHeaders(),
      });
      if (!response.ok) throw new ApiError("Metrics endpoint is unavailable.", response.status);
      const metrics = await response.text();
      return {
        requests: metricTotal(metrics, "hasamex_http_requests_total"),
        retrievals: metricTotal(metrics, "hasamex_retrieval_requests_total"),
        verifiedCitations: metricTotal(metrics, "hasamex_citations_total", 'outcome="verified"'),
        rejectedCitations: metricTotal(metrics, "hasamex_citations_total", 'outcome="rejected"'),
      };
    }, signal);
  },
  chat: async (question: string): Promise<ChatResponse> => {
    if (!API_BASE) {
      throw new ApiError("The application is missing NEXT_PUBLIC_API_BASE. Configure the deployed backend URL and rebuild.");
    }
    return withTimeout(async (signal) => {
      const res = await fetch(`${API_BASE}/api/projects/Robotics/ask`, {
        method: "POST",
        signal,
        headers: { "Content-Type": "application/json", ...(await authHeaders()) },
        body: JSON.stringify({ question }),
      });
      if (res.status === 401) throw new ApiError("Your session has expired. Please sign in again.", 401);
      if (!res.ok) throw new ApiError("Unable to answer that question right now.", res.status);
      return res.json() as Promise<ChatResponse>;
    });
  },
};
