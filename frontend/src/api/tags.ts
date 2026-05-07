import { api } from './client';
import type {
  TagResponse,
  TagListResponse,
  CreateTagRequest,
  UpdateTagRequest,
} from '@/types/api';

export const tagsApi = {
  list: (params?: { limit?: number; offset?: number; search?: string }) =>
    api.get<TagListResponse>('/api/tags', { params }).then((r) => r.data),

  get: (id: string) =>
    api.get<TagResponse>(`/api/tags/${id}`).then((r) => r.data),

  create: (data: CreateTagRequest) =>
    api.post<TagResponse>('/api/tags', data).then((r) => r.data),

  update: (id: string, data: UpdateTagRequest) =>
    api.put<TagResponse>(`/api/tags/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    api.delete(`/api/tags/${id}`),
};
