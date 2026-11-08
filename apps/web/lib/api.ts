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

/** Carries the API's own `detail` message so screens can show it as-is. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData;
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    // FormData sets its own multipart boundary header.
    headers: { ...(isForm ? {} : { "Content-Type": "application/json" }), ...init?.headers },
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

// --- KYC ---------------------------------------------------------------------

export type DocType = "gst_certificate" | "udyam_certificate" | "signatory_id" | "address_proof";
export type CheckResult = "pass" | "fail" | "review";

export interface Check {
  name: string;
  result: CheckResult;
  reason: string;
}

export interface KycDocument {
  id: number;
  doc_type: DocType;
  file: { file_type: string; size: string };
  uploaded_at: string;
  processing?: boolean;
  result: CheckResult | "processing";
  checks: Check[];
}

export interface KycStatus {
  business_id: number;
  name: string | null;
  gstin: string | null;
  udyam_number: string | null;
  identity: { result: CheckResult; checks: Check[] };
  documents: KycDocument[];
  required: DocType[];
  missing: DocType[];
  overall: "incomplete" | "review" | "fail" | "pass" | "processing";
  reasons: string[];
  consent: { kyc: boolean; marketing: boolean };
}

export interface KycCase {
  businessId: number;
  token: string;
}

export const kycHeaders = (c: KycCase) => ({ "X-KYC-Token": c.token });

export const api = {
  previewQuote: (profile: Profile) =>
    request<QuotePreview>("/quotes/preview", { method: "POST", body: JSON.stringify(profile) }),

  giveConsent: (
    body: { kyc: boolean; marketing: boolean; language: string } & (
      | { profile: Omit<Profile, "gstin">; business_id?: undefined }
      | { business_id: number; profile?: undefined }
    ),
    existing?: KycCase,
  ) =>
    request<{ business_id: number; token: string }>("/kyc/consent", {
      method: "POST",
      headers: existing ? kycHeaders(existing) : {},
      body: JSON.stringify(body),
    }).then((r): KycCase => ({ businessId: r.business_id, token: r.token })),

  setIdentity: (c: KycCase, body: { gstin: string | null; udyam_number: string | null }) =>
    request<{ name: string | null; result: CheckResult; checks: Check[] }>(`/kyc/${c.businessId}/identity`, {
      method: "PUT",
      headers: kycHeaders(c),
      body: JSON.stringify(body),
    }),

  uploadDocument: (c: KycCase, docType: DocType, file: File) => {
    const form = new FormData();
    form.append("business_id", String(c.businessId));
    form.append("doc_type", docType);
    form.append("file", file);
    return request<KycDocument>("/kyc/documents", { method: "POST", headers: kycHeaders(c), body: form });
  },

  kycStatus: (c: KycCase) => request<KycStatus>(`/kyc/${c.businessId}/status`, { headers: kycHeaders(c) }),

  withdrawConsent: (c: KycCase, purpose: "kyc" | "marketing") =>
    request<{ documents_deleted: number }>(`/kyc/${c.businessId}/consent/withdraw`, {
      method: "POST",
      headers: kycHeaders(c),
      body: JSON.stringify({ purpose }),
    }),
};
