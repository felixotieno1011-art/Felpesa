const BASE = "/api";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

let memoryToken: string | null = null;
let refreshing: Promise<string | null> | null = null;

export function setMemoryToken(t: string | null) {
  memoryToken = t;
}

/** One shared in-flight refresh, so parallel callers never replay the same cookie. */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include" })
      .then(async (r) => {
        if (!r.ok) return null;
        const j = (await r.json()) as { access_token: string };
        memoryToken = j.access_token;
        return j.access_token;
      })
      .catch(() => null)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

export async function api<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (options.token) headers["Authorization"] = `Bearer ${options.token}`;

  let res = await fetch(`${BASE}${path}`, { ...options, headers, credentials: "include" });
  if (res.status === 401 && options.token && !path.startsWith("/auth/")) {
    const fresh = await refreshAccessToken();
    if (fresh) {
      window.dispatchEvent(new CustomEvent("felpesa-token", { detail: fresh }));
      headers["Authorization"] = `Bearer ${fresh}`;
      res = await fetch(`${BASE}${path}`, { ...options, headers, credentials: "include" });
    }
  }

  let body: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!res.ok) {
    const msg =
      typeof body === "object" && body && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `HTTP ${res.status}`;
    if (res.status === 401 && options.token) {
      window.dispatchEvent(new Event("felpesa-unauthorized"));
    }
    if (res.status === 401 && options.token) {
      window.dispatchEvent(new Event("felpesa-unauthorized"));
    }
    throw new ApiError(res.status, msg, body);
  }
  return body as T;
}

// ---- types ----
export type Wallet = {
  id: string;
  user_id: string;
  currency: string;
  balance: string;
  status: string;
};

export type Transaction = {
  id: string;
  type: string;
  status: string;
  amount: string;
  currency: string;
  from_wallet_id: string | null;
  to_wallet_id: string | null;
  initiated_by: string;
  description: string | null;
  flagged_fraud: boolean;
  fraud_reason: string | null;
  created_at: string;
  completed_at: string | null;
  message?: string | null;
};

export type Paginated<T> = {
  items: T[];
  meta: { total: number; limit: number; offset: number };
};

export type TokenResponse = { access_token: string; token_type: string };

export type RegisterResponse = {
  id: string;
  phone: string;
  full_name: string;
  wallet_id: string;
};
