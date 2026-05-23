import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/stores/auth';

// Use Vite env var BACKEND_API_URL if provided at build time, otherwise default to same-origin '/'.
// For dev the vite server config already proxies '/api' -> http://localhost:8000.
const BASE_URL = (import.meta.env as any).BACKEND_API_URL ?? '/';

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !original._retry) {
      // The refresh endpoint itself returned 401 — no valid refresh token cookie.
      // Skip retry+redirect entirely so the caller's .catch() handles it cleanly.
      // Without this guard, every page load after logout triggers an infinite
      // reload loop: refresh fails → redirect to /auth/login → page reloads →
      // refresh fails again → ...
      if (original.url?.includes('/api/auth/refresh')) {
        return Promise.reject(error);
      }

      original._retry = true;

      if (!refreshPromise) {
        refreshPromise = refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }

      const newToken = await refreshPromise;
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }

      useAuthStore.getState().logout();
      window.location.href = '/auth/login';
    }

    return Promise.reject(error);
  },
);

async function refreshAccessToken(): Promise<string | null> {
  try {
    const res = await axios.post<{ access_token: string }>(
      '/api/auth/refresh',
      {},
      { withCredentials: true },
    );
    const token = res.data.access_token;
    useAuthStore.getState().setAccessToken(token);
    return token;
  } catch {
    return null;
  }
}

export function isAxiosError(e: unknown): e is AxiosError {
  return axios.isAxiosError(e);
}
