import { api } from './client';
import type {
  RegisterRequest,
  LoginRequest,
  TokenResponse,
  UserResponse,
  ConfirmEmailRequest,
  RequestPasswordResetRequest,
  ResendConfirmationRequest,
  ResetPasswordRequest,
  MessageResponse,
} from '@/types/api';

export const authApi = {
  register: (data: RegisterRequest) =>
    api.post<MessageResponse>('/api/auth/register', data).then((r) => r.data),

  login: (data: LoginRequest) =>
    api.post<TokenResponse>('/api/auth/login', data).then((r) => r.data),

  logout: () =>
    api.post<MessageResponse>('/api/auth/logout').then((r) => r.data),

  refresh: () =>
    api.post<TokenResponse>('/api/auth/refresh').then((r) => r.data),

  me: () =>
    api.get<UserResponse>('/api/auth/me').then((r) => r.data),

  confirmEmail: (data: ConfirmEmailRequest) =>
    api.post<MessageResponse>('/api/auth/confirm-email', data).then((r) => r.data),

  requestPasswordReset: (data: RequestPasswordResetRequest) =>
    api.post<MessageResponse>('/api/auth/request-password-reset', data).then((r) => r.data),

  resetPassword: (data: ResetPasswordRequest) =>
    api.post<MessageResponse>('/api/auth/reset-password', data).then((r) => r.data),

  resendConfirmation: (data: ResendConfirmationRequest) =>
    api.post<MessageResponse>('/api/auth/resend-confirmation', data).then((r) => r.data),
};
