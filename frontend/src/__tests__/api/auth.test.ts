import { authApi } from '@/api/auth';
import { api } from '@/api/client';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
  isAxiosError: vi.fn(),
}));

// Cast to any — vi.mocked() doesn't resolve mock helpers on overloaded axios types
const m = api as any;
const res = (data: unknown) => Promise.resolve({ data });

beforeEach(() => { vi.clearAllMocks(); });

describe('authApi', () => {
  it('login: POSTs to /api/auth/login and returns token', async () => {
    m.post.mockReturnValue(res({ access_token: 'tok', token_type: 'bearer' }));

    const result = await authApi.login({ email: 'a@b.com', password: 'pass' });

    expect(m.post).toHaveBeenCalledWith('/api/auth/login', { email: 'a@b.com', password: 'pass' });
    expect(result.access_token).toBe('tok');
  });

  it('register: POSTs to /api/auth/register', async () => {
    m.post.mockReturnValue(res({ message: 'ok' }));

    await authApi.register({ email: 'a@b.com', password: 'pass', nickname: 'alice' });

    expect(m.post).toHaveBeenCalledWith('/api/auth/register', {
      email: 'a@b.com', password: 'pass', nickname: 'alice',
    });
  });

  it('logout: POSTs to /api/auth/logout', async () => {
    m.post.mockReturnValue(res({ message: 'ok' }));

    await authApi.logout();

    expect(m.post).toHaveBeenCalledWith('/api/auth/logout');
  });

  it('refresh: POSTs to /api/auth/refresh and returns new token', async () => {
    m.post.mockReturnValue(res({ access_token: 'new', token_type: 'bearer' }));

    const result = await authApi.refresh();

    expect(m.post).toHaveBeenCalledWith('/api/auth/refresh');
    expect(result.access_token).toBe('new');
  });

  it('me: GETs /api/auth/me and returns user', async () => {
    const user = { id: 'u1', email: 'a@b.com', nickname: 'alice', role: 'user' };
    m.get.mockReturnValue(res(user));

    const result = await authApi.me();

    expect(m.get).toHaveBeenCalledWith('/api/auth/me');
    expect(result).toEqual(user);
  });

  it('confirmEmail: POSTs to /api/auth/confirm-email', async () => {
    m.post.mockReturnValue(res({ message: 'confirmed' }));

    await authApi.confirmEmail({ token: 'abc123' });

    expect(m.post).toHaveBeenCalledWith('/api/auth/confirm-email', { token: 'abc123' });
  });

  it('requestPasswordReset: POSTs to /api/auth/request-password-reset', async () => {
    m.post.mockReturnValue(res({ message: 'sent' }));

    await authApi.requestPasswordReset({ email: 'a@b.com' });

    expect(m.post).toHaveBeenCalledWith('/api/auth/request-password-reset', { email: 'a@b.com' });
  });

  it('resetPassword: POSTs to /api/auth/reset-password', async () => {
    m.post.mockReturnValue(res({ message: 'done' }));

    await authApi.resetPassword({ token: 'tok', new_password: 'newpass' });

    expect(m.post).toHaveBeenCalledWith('/api/auth/reset-password', {
      token: 'tok', new_password: 'newpass',
    });
  });

  it('resendConfirmation: POSTs to /api/auth/resend-confirmation', async () => {
    m.post.mockReturnValue(res({ message: 'sent' }));

    await authApi.resendConfirmation({ email: 'a@b.com' });

    expect(m.post).toHaveBeenCalledWith('/api/auth/resend-confirmation', { email: 'a@b.com' });
  });
});
