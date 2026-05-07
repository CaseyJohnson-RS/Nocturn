import { api } from './client';
import { useAuthStore } from '@/stores/auth';
import type {
  SessionResponse,
  SessionListResponse,
  CreateSessionRequest,
  UpdateSessionRequest,
  AIMessageResponse,
  MessagesListResponse,
  SendMessageRequest,
  UpdateActionRequest,
  SSEEventType,
  SSETextDelta,
  SSEError,
  SSEDone,
  Proposal,
  PendingConfirmation,
} from '@/types/api';

export const aiApi = {
  listSessions: (params?: { limit?: number; offset?: number }) =>
    api.get<SessionListResponse>('/api/ai/sessions', { params }).then((r) => r.data),

  createSession: (data: CreateSessionRequest = {}) =>
    api.post<SessionResponse>('/api/ai/sessions', data).then((r) => r.data),

  updateSession: (id: string, data: UpdateSessionRequest) =>
    api.put<SessionResponse>(`/api/ai/sessions/${id}`, data).then((r) => r.data),

  deleteSession: (id: string) =>
    api.delete(`/api/ai/sessions/${id}`),

  getMessages: (sessionId: string, params?: { limit?: number; offset?: number }) =>
    api
      .get<MessagesListResponse>(`/api/ai/sessions/${sessionId}/messages`, { params })
      .then((r) => r.data),

  updateAction: (sessionId: string, messageId: string, actionId: string, data: UpdateActionRequest) =>
    api
      .patch<AIMessageResponse>(
        `/api/ai/sessions/${sessionId}/messages/${messageId}/actions/${actionId}`,
        data,
      )
      .then((r) => r.data),

  cancelGeneration: (sessionId: string) =>
    api.post(`/api/ai/sessions/${sessionId}/cancel`),

  dismissBulk: (sessionId: string, confirmationId: string) =>
    api.post<AIMessageResponse>(`/api/ai/sessions/${sessionId}/dismiss/${confirmationId}`).then((r) => r.data),
};

// ── SSE stream helpers ─────────────────────────────────────────────────────────

export interface SSEFrame {
  event: SSEEventType;
  data: SSETextDelta | Proposal | PendingConfirmation | SSEError | SSEDone;
}

function* parseChunks(buffer: string): Generator<SSEFrame> {
  const chunks = buffer.split('\n\n');
  for (const chunk of chunks) {
    if (!chunk.trim()) continue;
    let event = '';
    let dataLine = '';
    for (const line of chunk.split('\n')) {
      if (line.startsWith('event: ')) event = line.slice(7).trim();
      else if (line.startsWith('data: ')) dataLine = line.slice(6).trim();
    }
    if (event && dataLine) {
      try {
        yield { event: event as SSEEventType, data: JSON.parse(dataLine) as SSEFrame['data'] };
      } catch {
        // malformed frame — skip
      }
    }
  }
}

async function* parseSSE(response: Response): AsyncGenerator<SSEFrame> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      // Flush decoder and process any remaining buffered event
      buffer += decoder.decode();
      if (buffer.trim()) yield* parseChunks(buffer + '\n\n');
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() ?? '';
    yield* parseChunks(chunks.join('\n\n'));
  }
}

async function* sendSSERequest(
  url: string,
  method: string,
  body?: unknown,
  signal?: AbortSignal,
): AsyncGenerator<SSEFrame> {
  const token = useAuthStore.getState().accessToken;
  const response = await fetch(url, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    credentials: 'include',
    signal,
  });

  if (!response.ok) {
    const err: unknown = await response.json().catch(() => ({}));
    throw { status: response.status, data: err };
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('text/event-stream')) {
    const err: unknown = await response.json().catch(() => ({}));
    throw { status: response.status, data: err };
  }

  yield* parseSSE(response);
}

export function sendMessage(
  sessionId: string,
  data: SendMessageRequest,
  signal?: AbortSignal,
): AsyncGenerator<SSEFrame> {
  return sendSSERequest(
    `/api/ai/sessions/${sessionId}/messages`,
    'POST',
    data,
    signal,
  );
}

export function confirmBulkStream(
  sessionId: string,
  confirmationId: string,
  signal?: AbortSignal,
): AsyncGenerator<SSEFrame> {
  return sendSSERequest(
    `/api/ai/sessions/${sessionId}/confirm/${confirmationId}`,
    'POST',
    undefined,
    signal,
  );
}
