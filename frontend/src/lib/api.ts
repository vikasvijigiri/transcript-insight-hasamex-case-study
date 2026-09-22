const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

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
};

export type ThemesResponse = {
  common_themes: string;
  disagreements: string;
  citations: Citation[];
};

export type ChatResponse = {
  answer: string;
  citations: Citation[];
};

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

export const api = {
  listExperts: () => getJSON<ExpertMeta[]>("/api/experts"),
  expertQA: (expertId: string) => getJSON<ExpertQAResponse>(`/api/experts/${expertId}/qa`),
  themes: () => getJSON<ThemesResponse>("/api/themes"),
  chat: async (question: string): Promise<ChatResponse> => {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) throw new Error(`chat failed: ${res.status}`);
    return res.json();
  },
};
