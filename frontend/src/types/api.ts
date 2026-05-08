// ── Auth ──────────────────────────────────────────────────────────────────────

export interface RegisterRequest {
  email: string;
  password: string;
  nickname: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  nickname: string;
  role: 'user' | 'admin';
  is_email_confirmed: boolean;
  is_active: boolean;
  created_at: string;
}

export interface ConfirmEmailRequest {
  token: string;
}

export interface RequestPasswordResetRequest {
  email: string;
}

export interface ResendConfirmationRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface MessageResponse {
  message: string;
}

// ── Profile ───────────────────────────────────────────────────────────────────

export interface UpdateNicknameRequest {
  nickname: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface DeleteAccountRequest {
  password: string;
}

// ── Notes ─────────────────────────────────────────────────────────────────────

export interface TagBrief {
  id: string;
  name: string;
}

export interface NoteResponse {
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
  tags: TagBrief[];
}

export interface NoteListResponse {
  items: NoteListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface NoteSearchResponse {
  items: NoteListItem[];
  total: number;
  limit: number;
  keywords: string[];
}

export interface CreateNoteRequest {
  title?: string | null;
  content?: string | null;
  tag_ids?: string[];
}

export interface UpdateNoteRequest {
  title?: string | null;
  content?: string | null;
  version: number;
}

export interface UpdateNoteTagsRequest {
  tag_ids: string[];
}

export interface BatchGetNotesRequest {
  note_ids: string[];
}

export interface BatchNotesResponse {
  items: NoteResponse[];
}

// ── Tags ──────────────────────────────────────────────────────────────────────

export interface TagResponse {
  id: string;
  user_id: string;
  name: string;
  created_at: string;
}

export interface TagListResponse {
  items: TagResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreateTagRequest {
  name: string;
}

export interface UpdateTagRequest {
  name: string;
}

// ── RAG ───────────────────────────────────────────────────────────────────────

export interface SearchRequest {
  query: string;
  limit?: number;
}

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

// ── AI ────────────────────────────────────────────────────────────────────────

export interface SessionResponse {
  id: string;
  user_id: string;
  title: string | null;
  created_at: string;
  last_message_at: string | null;
}

export interface SessionListResponse {
  items: SessionResponse[];
  total: number;
}

export interface CreateSessionRequest {
  dismiss_session_id?: string | null;
}

export interface UpdateSessionRequest {
  title: string;
}

export type ProposalType =
  | 'edit_note'
  | 'create_note'
  | 'delete_note'
  | 'add_tags'
  | 'remove_tags';
export type ProposalStatus = 'pending' | 'applied' | 'dismissed';
export type ConfirmationStatus = 'pending' | 'confirmed' | 'dismissed';

export interface Proposal {
  id: string;
  type: 'proposal';
  proposal_type: ProposalType;
  status: ProposalStatus;
  note_id: string | null;
  data: Record<string, unknown>;
  summary: string | null;
}

export interface PendingConfirmation {
  id: string;
  type: 'pending_confirmation';
  status: ConfirmationStatus;
  operation_type: string;
  note_ids: string[];
  params: Record<string, unknown>;
  summary: string;
}

export type Action = Proposal | PendingConfirmation;

export interface AIMessageResponse {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  actions: Action[] | null;
  attached_note_ids: string[] | null;
  created_at: string;
}

export interface MessagesListResponse {
  items: AIMessageResponse[];
  total: number;
}

export interface SendMessageRequest {
  content: string;
  attached_note_ids?: string[];
}

export interface UpdateActionRequest {
  status: 'applied' | 'dismissed';
}

// SSE events
export type SSEEventType =
  | 'ai:text_delta'
  | 'ai:proposal'
  | 'ai:pending_confirmation'
  | 'ai:error'
  | 'ai:done';

export interface SSETextDelta {
  delta: string;
}
export interface SSEError {
  code: string;
  message: string;
}
export interface SSEDone {
  message: AIMessageResponse;
}

// ── Admin ─────────────────────────────────────────────────────────────────────

export interface UserListItem {
  id: string;
  email: string;
  nickname: string;
  role: 'user' | 'admin';
  is_email_confirmed: boolean;
  is_active: boolean;
  created_at: string;
}

export interface UserListResponse {
  items: UserListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface SetActiveRequest {
  is_active: boolean;
}

export interface SetRoleRequest {
  role: 'user' | 'admin';
}

// ── Common ────────────────────────────────────────────────────────────────────

export interface APIError {
  status: number;
  data: unknown;
}
