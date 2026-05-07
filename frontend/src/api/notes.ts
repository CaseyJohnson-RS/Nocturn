import { api } from './client';
import type {
  NoteResponse,
  NoteListResponse,
  NoteSearchResponse,
  CreateNoteRequest,
  UpdateNoteRequest,
  UpdateNoteTagsRequest,
  BatchGetNotesRequest,
  BatchNotesResponse,
} from '@/types/api';

export const notesApi = {
  list: (params?: {
    limit?: number;
    offset?: number;
    deleted?: boolean;
    search?: string;
    tag_ids?: string;
  }) => api.get<NoteListResponse>('/api/notes', { params }).then((r) => r.data),

  search: (keywords: string, limit = 50) =>
    api
      .get<NoteSearchResponse>('/api/notes/search', { params: { keywords, limit } })
      .then((r) => r.data),

  get: (id: string) =>
    api.get<NoteResponse>(`/api/notes/${id}`).then((r) => r.data),

  create: (data: CreateNoteRequest) =>
    api.post<NoteResponse>('/api/notes', data).then((r) => r.data),

  update: (id: string, data: UpdateNoteRequest) =>
    api.put<NoteResponse>(`/api/notes/${id}`, data).then((r) => r.data),

  delete: (id: string, permanent = false) =>
    api.delete(`/api/notes/${id}`, { params: { permanent } }),

  restore: (id: string) =>
    api.post<NoteResponse>(`/api/notes/${id}/restore`).then((r) => r.data),

  setTags: (id: string, data: UpdateNoteTagsRequest) =>
    api.put<NoteResponse>(`/api/notes/${id}/tags`, data).then((r) => r.data),

  batch: (data: BatchGetNotesRequest) =>
    api.post<BatchNotesResponse>('/api/notes/batch', data).then((r) => r.data),
};
