import type { AgentLog, ApprovalQueueItem, Campaign, CampaignCalendar, Post } from "./types";

// Generic fetch wrapper exposed as a convenience object for page components.
export const apiClient = {
  get:   <T>(path: string)                  => req<T>(path),
  post:  <T>(path: string, body?: unknown)   => req<T>(path, { method: "POST",  body: body  != null ? JSON.stringify(body)  : undefined }),
  patch: <T>(path: string, body?: unknown)   => req<T>(path, { method: "PATCH", body: body  != null ? JSON.stringify(body)  : undefined }),
  del:   <T>(path: string)                  => req<T>(path, { method: "DELETE" }),
};

// Convenience login that calls the auth endpoint and stores the token.
export async function login(password: string): Promise<void> {
  const { access_token, expires_in } = await req<{
    access_token: string; token_type: string; expires_in: number;
  }>("/auth/token", { method: "POST", body: JSON.stringify({ password }) });

  if (typeof window !== "undefined") {
    localStorage.setItem("hexa_portal_token",  access_token);
    localStorage.setItem("hexa_portal_expiry", String(Date.now() + expires_in * 1000));
    document.cookie = `portal_token=1; path=/; max-age=${expires_in}; samesite=lax`;
  }
}

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token =
    typeof window !== "undefined"
      ? (localStorage.getItem("hexa_token") ?? localStorage.getItem("hexa_portal_token"))
      : null;

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (res.status === 401 && typeof window !== "undefined") {
    localStorage.removeItem("hexa_portal_token");
    document.cookie = "portal_token=; path=/; max-age=0";
    window.location.href = "/login";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? res.statusText);
  }

  // 204 No Content — return empty object so callers don't need to handle undefined
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as unknown as T;
  }

  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export const auth = {
  login: (password: string) =>
    req<{ access_token: string; token_type: string; expires_in: number }>(
      "/auth/token",
      { method: "POST", body: JSON.stringify({ password }) }
    ),
};

// ── Campaigns ─────────────────────────────────────────────────────────────────
export const campaigns = {
  list: (params?: { skip?: number; limit?: number; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.skip)   qs.set("skip",   String(params.skip));
    if (params?.limit)  qs.set("limit",  String(params.limit));
    if (params?.status) qs.set("status", params.status);
    return req<Campaign[]>(`/campaigns?${qs}`);
  },
  create: (data: {
    name: string; brief: string; objective: string;
    kpis: Record<string, unknown>;
    start_date: string; end_date: string; platforms: string[];
  }) => req<Campaign>("/campaigns", { method: "POST", body: JSON.stringify(data) }),
  get:         (id: string) => req<Campaign>(`/campaigns/${id}`),
  getCalendar: (id: string) => req<CampaignCalendar>(`/campaigns/${id}/calendar`),
  getBilingual:(id: string) => req<unknown>(`/campaigns/${id}/bilingual-view`),
};

// ── Posts ─────────────────────────────────────────────────────────────────────
export const posts = {
  get:  (id: string) => req<Post>(`/posts/${id}`),
  update: (id: string, data: { copy?: string; scheduled_at?: string }) =>
    req<Post>(`/posts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  approve: (id: string, feedback?: string) =>
    req<Post>(`/posts/${id}/approve`, {
      method: "POST", body: JSON.stringify({ feedback }),
    }),
  reject: (id: string, feedback: string) =>
    req<Post>(`/posts/${id}/reject`, {
      method: "POST", body: JSON.stringify({ feedback }),
    }),
};

// ── Approvals ─────────────────────────────────────────────────────────────────
export const approvals = {
  queue: (params?: { skip?: number; limit?: number; platform?: string }) => {
    const qs = new URLSearchParams();
    if (params?.skip)     qs.set("skip",     String(params.skip));
    if (params?.limit)    qs.set("limit",    String(params.limit));
    if (params?.platform) qs.set("platform", params.platform);
    return req<ApprovalQueueItem[]>(`/approvals/queue?${qs}`);
  },
};

// ── Agent logs ────────────────────────────────────────────────────────────────
export const agentLogs = {
  list: (params?: {
    agent_name?: string; status?: string;
    from_date?: string; to_date?: string;
    skip?: number; limit?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.agent_name) qs.set("agent_name", params.agent_name);
    if (params?.status)     qs.set("status",     params.status);
    if (params?.from_date)  qs.set("from_date",  params.from_date);
    if (params?.to_date)    qs.set("to_date",    params.to_date);
    if (params?.skip)       qs.set("skip",       String(params.skip));
    if (params?.limit)      qs.set("limit",      String(params.limit));
    return req<AgentLog[]>(`/agent-logs?${qs}`);
  },
};

// ── Tools ─────────────────────────────────────────────────────────────────────
export const tools = {
  checkCompliance: (text: string, language = "zh-CN") =>
    req<{ passed: boolean; flags: unknown[]; suggestions: string[] }>(
      "/compliance/check",
      { method: "POST", body: JSON.stringify({ text, language }) }
    ),
};
