import { api } from './client';
import type {
  UserListResponse,
  UserListItem,
  SetActiveRequest,
  SetRoleRequest,
} from '@/types/api';

export const adminApi = {
  listUsers: (params?: { limit?: number; offset?: number; search?: string }) =>
    api.get<UserListResponse>('/api/admin/users', { params }).then((r) => r.data),

  getUser: (id: string) =>
    api.get<UserListItem>(`/api/admin/users/${id}`).then((r) => r.data),

  setActive: (id: string, data: SetActiveRequest) =>
    api.put<UserListItem>(`/api/admin/users/${id}/active`, data).then((r) => r.data),

  setRole: (id: string, data: SetRoleRequest) =>
    api.put<UserListItem>(`/api/admin/users/${id}/role`, data).then((r) => r.data),

  deleteUser: (id: string) =>
    api.delete<void>(`/api/admin/users/${id}`).then((r) => r.data),
};
