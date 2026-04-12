import { apiFetch, apiPost, apiPut, apiDelete } from "./client";
import type { Note, NoteListResponse } from "./types";

export async function listNotes(params?: {
  limit?: number;
  offset?: number;
  deleted?: boolean;
  search?: string;
  tag_ids?: string[];
}): Promise<NoteListResponse> {
  const sp = new URLSearchParams();
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  if (params?.deleted) sp.set("deleted", "true");
  if (params?.search) sp.set("search", params.search);
  if (params?.tag_ids?.length) sp.set("tag_ids", params.tag_ids.join(","));
  const qs = sp.toString();
  return apiFetch(`/api/notes${qs ? `?${qs}` : ""}`);
}

export async function getNote(noteId: string): Promise<Note> {
  return apiFetch(`/api/notes/${noteId}`);
}

export async function createNote(body: {
  title?: string | null;
  content?: string | null;
  tag_ids?: string[];
}): Promise<Note> {
  return apiPost("/api/notes", body);
}

export async function updateNote(
  noteId: string,
  body: { title?: string | null; content?: string | null; version: number },
  init?: RequestInit,
): Promise<Note> {
  return apiPut(`/api/notes/${noteId}`, body, init);
}

export async function deleteNote(noteId: string): Promise<void> {
  return apiDelete(`/api/notes/${noteId}`);
}

export async function restoreNote(noteId: string): Promise<Note> {
  return apiPost(`/api/notes/${noteId}/restore`);
}

export async function updateNoteTags(
  noteId: string,
  tagIds: string[],
): Promise<Note> {
  return apiPut(`/api/notes/${noteId}/tags`, { tag_ids: tagIds });
}
