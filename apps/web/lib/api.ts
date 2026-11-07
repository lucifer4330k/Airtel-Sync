const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type Segment = "micro" | "prof" | "multi" | "mfg";

export interface Profile {
  segment: Segment;
  city_tier: 1 | 2;
  employees: number;
  sites: number;
  gstin?: string | null;
}

export interface LineItem {
  product_id: string;
  name: string;
  unit: string;
  qty: number;
  unit_price: number;
  monthly: number;
  setup: number;
  is_addon: boolean;
}

export interface PricedBundle {
  tier: "good" | "better" | "best" | "custom";
  items: LineItem[];
  monthly_total: number;
  setup_total: number;
  contract_months: number;
  eta_days: number;
}

export interface QuotePreview {
  gstin_active: boolean;
  tiers: PricedBundle[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  previewQuote: (profile: Profile) =>
    request<QuotePreview>("/quotes/preview", { method: "POST", body: JSON.stringify(profile) }),
};
