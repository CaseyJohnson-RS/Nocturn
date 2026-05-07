import { useAuthStore } from '@/stores/auth';
import type { UserResponse } from '@/types/api';

const mockUser: UserResponse = {
  id: 'u1',
  email: 'test@example.com',
  nickname: 'tester',
  role: 'user',
  is_email_confirmed: true,
  is_active: true,
  created_at: '2024-01-01T00:00:00Z',
};

beforeEach(() => {
  useAuthStore.setState({ user: null, accessToken: null, isInitialized: false });
});

describe('Auth store – initial state', () => {
  it('starts with no user', () => {
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('starts with no access token', () => {
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it('starts uninitialised', () => {
    expect(useAuthStore.getState().isInitialized).toBe(false);
  });
});

describe('Auth store – mutations', () => {
  it('setUser stores the user', () => {
    useAuthStore.getState().setUser(mockUser);
    expect(useAuthStore.getState().user).toEqual(mockUser);
  });

  it('setAccessToken stores the token', () => {
    useAuthStore.getState().setAccessToken('tok-abc');
    expect(useAuthStore.getState().accessToken).toBe('tok-abc');
  });

  it('setInitialized flips isInitialized to true', () => {
    useAuthStore.getState().setInitialized();
    expect(useAuthStore.getState().isInitialized).toBe(true);
  });

  it('logout clears user and token', () => {
    useAuthStore.setState({ user: mockUser, accessToken: 'tok' });
    useAuthStore.getState().logout();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it('logout does NOT reset isInitialized (by design)', () => {
    // After logout the app stays "initialized" – the router decides where to go
    useAuthStore.setState({ isInitialized: true });
    useAuthStore.getState().logout();
    expect(useAuthStore.getState().isInitialized).toBe(true);
  });
});
