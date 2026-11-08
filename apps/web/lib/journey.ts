/** Advisor, persisted quotes, checkout and order tracking. */

import { request, type Segment } from "@/lib/api";

// --- owner session (tab-scoped; replaced by OTP login + JWT later) ------------

export interface OwnerSession {
  businessId: number;
  token: string;
}

const OWNER_KEY = "udyam.owner";
const PLAN_KEY = "udyam.plan";

function read<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown) {
  try {
    if (value === null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private mode */
  }
}

export const owner = {
  get: () => read<OwnerSession>(OWNER_KEY),
  set: (s: OwnerSession | null) => write(OWNER_KEY, s),
};

export interface PlanRef {
  quoteIds: number[];
  recommended: number;
}

export const plan = {
  get: () => read<PlanRef>(PLAN_KEY),
  set: (p: PlanRef | null) => write(PLAN_KEY, p),
};

export const lastOrder = {
  get: () => read<number>("udyam.order"),
  set: (id: number) => write("udyam.order", id),
};

const ownerHeaders = (s: OwnerSession) => ({ "X-Owner-Token": s.token });

// --- advisor -----------------------------------------------------------------

export interface BundleCard {
  business_id: number;
  owner_token: string;
  recommended_quote_id: number;
  quotes: { id: number; tier: "good" | "better" | "best"; monthly_total: number; setup_total: number }[];
  reasons: { product: string; reason: string | null }[];
  notes: string[];
}

export interface AdvisorTurn {
  reply: string;
  chips: string[];
  done: boolean;
  bundle?: BundleCard | null;
  needs_human?: boolean;
  language?: string;
}

export const advisor = {
  start: (language?: string, channel: "web" | "voice" = "web") =>
    request<AdvisorTurn & { session_id: number; token: string }>("/advisor/sessions", {
      method: "POST",
      body: JSON.stringify({ channel, language }),
    }),
  send: (sessionId: number, token: string, text: string) =>
    request<AdvisorTurn>(`/advisor/sessions/${sessionId}/messages`, {
      method: "POST",
      headers: { "X-Session-Token": token },
      body: JSON.stringify({ text }),
    }),
};

// --- quotes ------------------------------------------------------------------

export interface QuoteItem {
  product_id: string;
  name: string;
  description: string;
  unit: string;
  qty: number;
  unit_price: number;
  monthly: number;
  setup: number;
  install_days: number;
  is_addon: boolean;
}

export interface AddonOption {
  product_id: string;
  name: string;
  description: string;
  category: string;
  included: boolean;
  qty: number;
  monthly_from: number;
  available: boolean;
  reason: string | null;
}

export interface Quote {
  id: number;
  tier: "good" | "better" | "best";
  status: "draft" | "accepted" | "superseded";
  business_id: number;
  items: QuoteItem[];
  monthly_total: number;
  setup_total: number;
  contract_months: number;
  eta_days: number;
  eta_date: string;
  share_token: string;
  siblings?: number[];
  addons: AddonOption[];
}

export const quotes = {
  create: (
    profile: { segment: Segment; city_tier: 1 | 2; employees: number; sites: number; gstin?: string | null },
    language?: string,
  ) =>
    request<{ business_id: number; owner_token: string; recommended: number; gstin_active: boolean; quotes: Quote[] }>(
      "/quotes",
      { method: "POST", body: JSON.stringify({ profile, language }) },
    ),
  get: (id: number, s: OwnerSession | null, share?: string) =>
    request<Quote>(`/quotes/${id}${share ? `?share=${encodeURIComponent(share)}` : ""}`, {
      headers: s ? ownerHeaders(s) : {},
    }),
  toggle: (id: number, s: OwnerSession, productId: string, include: boolean) =>
    request<Quote>(`/quotes/${id}/items`, {
      method: "PATCH",
      headers: ownerHeaders(s),
      body: JSON.stringify({ product_id: productId, include }),
    }),
  accept: (id: number, s: OwnerSession, body: { phone: string; payment_method: "upi_autopay" | "razorpay"; upi_id?: string }) =>
    request<{ order_id: number; payment_ref: string; owner_token: string }>(`/quotes/${id}/accept`, {
      method: "POST",
      headers: ownerHeaders(s),
      body: JSON.stringify(body),
    }),
};

// --- orders ------------------------------------------------------------------

export interface OrderView {
  id: number;
  state: string;
  state_label: string;
  hold_reason: string | null;
  eta_date: string | null;
  engineer_slot: string | null;
  steps: { state: string; label: string; done: boolean; current: boolean; at: string | null }[];
  events: { event: string; label: string; detail: string | null; at: string }[];
  items: { name: string; install_days: number }[];
  slot_options: { start: string; end: string }[];
  created_at: string;
}

export const orders = {
  get: (id: number, token: string) => request<OrderView>(`/orders/${id}`, { headers: { "X-Owner-Token": token } }),
  reschedule: (id: number, token: string, start: string) =>
    request<OrderView>(`/orders/${id}/reschedule`, {
      method: "POST",
      headers: { "X-Owner-Token": token },
      body: JSON.stringify({ start }),
    }),
};
