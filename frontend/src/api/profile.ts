import { api } from './client';
import type {
  UserResponse,
  UpdateNicknameRequest,
  ChangePasswordRequest,
  DeleteAccountRequest,
  MessageResponse,
} from '@/types/api';

export const profileApi = {
  updateNickname: (data: UpdateNicknameRequest) =>
    api.put<UserResponse>('/api/profile/nickname', data).then((r) => r.data),

  changePassword: (data: ChangePasswordRequest) =>
    api.put<MessageResponse>('/api/profile/password', data).then((r) => r.data),

  deleteAccount: (data: DeleteAccountRequest) =>
    api.post('/api/profile/delete_account', data),
};
