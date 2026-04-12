/**
 * HTTP client with JWT auth, auto-refresh, and typed error handling.
 */

let accessToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function refreshToken(): Promise<boolean> {
  try {
    const resp = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
    });
    if (!resp.ok) return false;
    const data = await resp.json();
    setAccessToken(data.access_token);
    return true;
  } catch {
    return false;
  }
}

async function ensureToken(): Promise<boolean> {
  if (accessToken) return true;
  if (!refreshPromise) {
    refreshPromise = refreshToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  await ensureToken();

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  if (options.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  let resp = await fetch(path, { ...options, headers, credentials: "include" });

  // Auto-refresh on 401
  if (resp.status === 401 && accessToken) {
    const refreshed = await refreshToken();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${accessToken}`;
      resp = await fetch(path, { ...options, headers, credentials: "include" });
    }
  }

  if (resp.status === 204) return undefined as T;

  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }

  return resp.json();
}

export function apiPost<T = unknown>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}

export function apiPut<T = unknown>(path: string, body: unknown, init: RequestInit = {}): Promise<T> {
  return apiFetch<T>(path, {
    method: "PUT",
    body: JSON.stringify(body),
    ...init,
  });
}

export function apiPatch<T = unknown>(path: string, body: unknown, init: RequestInit = {}): Promise<T> {
  return apiFetch<T>(path, {
    method: "PATCH",
    body: JSON.stringify(body),
    ...init,
  });
}

export function apiDelete(path: string): Promise<void> {
  return apiFetch(path, { method: "DELETE" });
}
