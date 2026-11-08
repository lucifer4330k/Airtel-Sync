/** Console API client. JWT lives in sessionStorage for this tab only. */

import { ApiError, request } from "@/lib/api";

const KEY = "udyam.console";

export interface ConsoleUser {
  username: string;
  name: string;
  role: "admin" | "rep" | "partner";
  city: string | null;
}

export const consoleSession = {
  get(): { token: string; user: ConsoleUser } | null {
    try {
      const raw = sessionStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },
  set(v: { token: string; user: ConsoleUser } | null) {
    try {
      if (v) sessionStorage.setItem(KEY, JSON.stringify(v));
      else sessionStorage.removeItem(KEY);
    } catch {
      /* private mode */
    }
  },
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const s = consoleSession.get();
  try {
    return await request<T>(`/console${path}`, {
      ...init,
      headers: { ...(s ? { Authorization: `Bearer ${s.token}` } : {}), ...init?.headers },
    });
  } catch (e) {
    if (e instanceof ApiError && e.status === 401 && typeof window !== "undefined") {
      consoleSession.set(null);
      window.location.href = "/console/login";
    }
    throw e;
  }
}

export interface Reason {
  feature: string;
  label: string;
  effect: "up" | "down";
  weight: number;
}

export interface LeadRow {
  id: number;
  external_id: string | null;
  business: string;
  type: string | null;
  segment: string;
  city: string | null;
  tier: number;
  employees: number;
  sites: number;
  source: string;
  stage: string;
  outcome: string | null;
  stopped_at: string | null;
  drop_reason: string | null;
  needs_human: boolean;
  needs_human_reason: string | null;
  products_of_interest: string[];
  score: number | null;
  reasons: Reason[];
  assigned_to: string | null;
  created_at: string;
  digital: boolean;
}

export interface LeadDetail extends LeadRow {
  phone: string | null;
  gstin: string | null;
  language: string | null;
  current_internet: string | null;
  telecom_spend: number | null;
  follow_ups: { at: string; by: string; note: string; outcome?: string | null }[];
  transcript: { role: string; text: string; at: string }[];
  quotes: { id: number; tier: string; status: string; monthly_total: number; setup_total: number }[];
  orders: { id: number; state_label: string; eta_date: string | null }[];
  kyc: { overall: string; reasons: string[]; missing: string[] } | null;
}

export interface Funnel {
  history: {
    stages: { stage: string; count: number }[];
    conversion: number;
    avg_days_to_activate: number;
    avg_follow_up_calls: number;
    cac: number;
    by_source: { source: string; leads: number; conversion: number; cac: number }[];
    drop_reasons: { reason: string; count: number }[];
  };
  live: { stages: { stage: string; count: number }[]; orders: number; activated: number; needs_human: number };
  credits: { username: string; name: string; role: string; city: string; digital_orders: number }[];
}

export interface QueueItem {
  check_id: number;
  check: string;
  reason: string;
  document_id: number;
  doc_type: string;
  business_id: number;
  business: string;
  city: string | null;
  lead_id: number | null;
  uploaded_at: string;
}

export interface ConsoleOrder {
  id: number;
  business: string;
  city: string | null;
  state: string;
  state_label: string;
  hold_reason: string | null;
  eta_date: string | null;
  engineer_slot: string | null;
  created_at: string;
}

export interface OutboxItem {
  id: number;
  order_id: number | null;
  channel: string;
  to: string | null;
  body: string;
  status: string;
  at: string;
}

export const consoleApi = {
  login: (username: string, password: string) =>
    request<{ token: string; user: ConsoleUser }>("/console/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  team: () => call<ConsoleUser[]>("/team"),
  leads: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== "") as [string, string][],
    );
    return call<{ total: number; page: number; items: LeadRow[] }>(`/leads?${qs}`);
  },
  lead: (id: number) => call<LeadDetail>(`/leads/${id}`),
  assign: (id: number, username: string) =>
    call<LeadRow>(`/leads/${id}/assign`, { method: "POST", body: JSON.stringify({ username }) }),
  followUp: (id: number, note: string, outcome?: string) =>
    call<LeadRow>(`/leads/${id}/follow-ups`, { method: "POST", body: JSON.stringify({ note, outcome: outcome || null }) }),
  funnel: () => call<Funnel>("/funnel"),
  queue: () => call<QueueItem[]>("/kyc/queue"),
  resolve: (checkId: number, result: "pass" | "fail", note: string) =>
    call<{ overall: string }>(`/kyc/checks/${checkId}/resolve`, { method: "POST", body: JSON.stringify({ result, note }) }),
  orders: () => call<ConsoleOrder[]>("/orders"),
  advance: (id: number) => call<ConsoleOrder>(`/orders/${id}/advance`, { method: "POST" }),
  hold: (id: number, reason: string) =>
    call<ConsoleOrder>(`/orders/${id}/hold`, { method: "POST", body: JSON.stringify({ reason }) }),
  outbox: () => call<OutboxItem[]>("/notifications"),
};
