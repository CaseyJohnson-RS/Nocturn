/* Shared API response types matching backend schemas */

export interface User {
  id: string;
  email: string;
  nickname: string;
  role: string;
  is_email_confirmed: boolean;
  is_active: boolean;
  created_at: string;
}

export interface TagBrief {
  id: string;
  name: string;
}

export interface Note {
  id: string;
  user_id: string;
  title: string | null;
  content: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  tags: TagBrief[];
}

export interface NoteListItem {
  id: string;
  title: string | null;
  updated_at: string;
  deleted_at: string | null;
}

export interface NoteListResponse {
  items: NoteListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface Tag {
  id: string;
  user_id: string;
  name: string;
  created_at: string;
}

export interface TagListResponse {
  items: Tag[];
  total: number;
}

// --- AI ---

export interface ChatSession {
  id: string;
  user_id: string;
  title: string | null;
  created_at: string;
  last_message_at: string | null;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  actions: Action[] | null;
  attached_note_ids: string[] | null;
  created_at: string;
}

export interface SessionListResponse {
  items: ChatSession[];
  total: number;
}

// --- Proposals & Actions ---

export interface Proposal {
  type: "proposal";
  id: string;
  proposal_type:
    | "edit_note"
    | "create_note"
    | "delete_note"
    | "add_tags"
    | "remove_tags";
  status: "pending" | "applied" | "dismissed";
  note_id: string | null;
  data: Record<string, unknown> | null;
  summary: string | null;
}

export interface PendingConfirmation {
  type: "pending_confirmation";
  id: string;
  status: "pending" | "confirmed" | "dismissed";
  operation_type: string;
  note_ids: string[];
  params: Record<string, unknown>;
  summary: string | null;
}

export type Action = Proposal | PendingConfirmation;

// --- RAG ---

export interface SearchResult {
  chunk_id: string;
  note_id: string;
  chunk_index: number;
  content: string;
  score: number | null;
}

export interface SearchResponse {
  results: SearchResult[];
}

// --- SSE events ---

export interface SSETextDelta {
  delta: string;
}

export interface SSEDone {
  message?: ChatMessage;
}

export interface SSEError {
  code: string;
  message: string;
}
