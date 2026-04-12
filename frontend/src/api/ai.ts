import { apiFetch, apiPost, apiPatch, apiDelete, getAccessToken } from "./client";
import type {
  ChatSession,
  SessionListResponse,
  ChatMessage,
} from "./types";

// --- Sessions ---

export async function createSession(
  dismissSessionId?: string,
): Promise<ChatSession> {
  return apiPost("/api/ai/sessions", {
    dismiss_session_id: dismissSessionId ?? null,
  });
}

export async function listSessions(): Promise<SessionListResponse> {
  return apiFetch("/api/ai/sessions");
}

export async function getSessionMessages(
  sessionId: string,
): Promise<{ items: ChatMessage[]; total: number }> {
  return apiFetch(`/api/ai/sessions/${sessionId}/messages`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  return apiDelete(`/api/ai/sessions/${sessionId}`);
}

// --- Message (SSE streaming) ---

export type SSECallback = (
  event: string | null,
  data: Record<string, unknown>,
) => void;

export async function sendMessage(
  sessionId: string,
  message: string,
  noteIds: string[],
  onEvent: SSECallback,
  signal?: AbortSignal,
): Promise<void> {
  const token = getAccessToken();
  const resp = await fetch(`/api/ai/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content: message, attached_note_ids: noteIds }),
    credentials: "include",
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`SSE failed: ${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent: string | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        currentEvent = null;
        continue;
      }
      if (trimmed.startsWith("event: ")) {
        currentEvent = trimmed.slice(7).trim();
      } else if (trimmed.startsWith("data: ")) {
        try {
          const data = JSON.parse(trimmed.slice(6));
          onEvent(currentEvent, data);
        } catch {
          /* ignore parse errors */
        }
        currentEvent = null;
      }
    }
  }
}

// --- Actions ---

export async function updateActionStatus(
  sessionId: string,
  messageId: string,
  actionId: string,
  status: "applied" | "dismissed",
): Promise<ChatMessage> {
  return apiPatch(
    `/api/ai/sessions/${sessionId}/messages/${messageId}/actions/${actionId}`,
    { status },
  );
}

// --- Bulk ---

export async function confirmBulk(
  sessionId: string,
  confirmationId: string,
  onEvent: SSECallback,
): Promise<void> {
  const token = getAccessToken();
  const resp = await fetch(
    `/api/ai/sessions/${sessionId}/confirm/${confirmationId}`,
    {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: "include",
    },
  );
  if (!resp.ok || !resp.body) throw new Error(`Bulk confirm failed: ${resp.status}`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent: string | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) { currentEvent = null; continue; }
      if (trimmed.startsWith("event: ")) currentEvent = trimmed.slice(7).trim();
      else if (trimmed.startsWith("data: ")) {
        try {
          onEvent(currentEvent, JSON.parse(trimmed.slice(6)));
        } catch { /* */ }
        currentEvent = null;
      }
    }
  }
}

export async function dismissBulk(
  sessionId: string,
  confirmationId: string,
): Promise<ChatMessage> {
  return apiPost(`/api/ai/sessions/${sessionId}/dismiss/${confirmationId}`);
}

export async function cancelGeneration(sessionId: string): Promise<void> {
  await apiPost(`/api/ai/sessions/${sessionId}/cancel`);
}
