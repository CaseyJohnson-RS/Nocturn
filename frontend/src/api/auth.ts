import { apiPost, apiFetch, setAccessToken } from "./client";
import type { User } from "./types";

export async function login(
  email: string,
  password: string,
): Promise<{ access_token: string; user: User }> {
  const data = await apiPost<{ access_token: string }>("/api/auth/login", {
    email,
    password,
  });
  setAccessToken(data.access_token);
  const user = await apiFetch<User>("/api/auth/me");
  return { access_token: data.access_token, user };
}

export async function register(
  email: string,
  password: string,
  nickname: string,
): Promise<void> {
  await apiPost("/api/auth/register", { email, password, nickname });
}

export async function logout(): Promise<void> {
  await apiPost("/api/auth/logout");
  setAccessToken(null);
}

export async function getMe(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}

export async function requestPasswordReset(email: string): Promise<void> {
  await apiPost("/api/auth/request-password-reset", { email });
}

export async function resetPassword(
  token: string,
  new_password: string,
): Promise<void> {
  await apiPost("/api/auth/reset-password", { token, new_password });
}

export async function confirmEmail(token: string): Promise<void> {
  await apiPost("/api/auth/confirm-email", { token });
}

export async function resendConfirmation(email: string): Promise<void> {
  await apiPost("/api/auth/resend-confirmation", { email });
}
