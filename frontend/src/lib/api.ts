import type { Asset, AssetOverview, MarketBrief, SignalEvent, SourceHealth } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

type LoginResponse = {
  username: string;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail || detail;
    } catch {
      // Response was not JSON.
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export function login(username: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
}

export function logout(): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>("/auth/logout", { method: "POST" });
}

export function me(): Promise<LoginResponse> {
  return request<LoginResponse>("/auth/me");
}

export function getAssets(): Promise<Asset[]> {
  return request<Asset[]>("/assets");
}

export function getMarketBrief(): Promise<MarketBrief> {
  return request<MarketBrief>("/market/brief");
}

export function getAssetOverview(symbol: string, window = "30d"): Promise<AssetOverview> {
  const params = new URLSearchParams({ window });
  return request<AssetOverview>(`/assets/${encodeURIComponent(symbol)}/overview?${params.toString()}`);
}

export function getEvents(filters: { symbol?: string; signal_type?: string; severity?: string }): Promise<SignalEvent[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<SignalEvent[]>(`/events${suffix}`);
}

export function getSourceHealth(): Promise<SourceHealth[]> {
  return request<SourceHealth[]>("/health/sources");
}

export function runCollection(): Promise<{ id: number; status: string; message: string; summary: Record<string, unknown> }> {
  return request<{ id: number; status: string; message: string; summary: Record<string, unknown> }>("/admin/collection-runs", { method: "POST" });
}

export function regenerateInterpretations(): Promise<{ id: number | null; status: string; message: string; summary: Record<string, unknown> }> {
  return request<{ id: number | null; status: string; message: string; summary: Record<string, unknown> }>(
    "/admin/interpretations/regenerate",
    { method: "POST" }
  );
}
