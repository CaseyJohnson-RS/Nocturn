import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';
import { api, isAxiosError } from '@/api/client';
import { useAuthStore } from '@/stores/auth';

// Two adapters: one for the `api` instance, one for bare `axios`.
// refreshAccessToken() uses axios.post (default instance), not api.post.
let apiMock: MockAdapter;
let axiosMock: MockAdapter;

beforeEach(() => {
  apiMock = new MockAdapter(api);
  axiosMock = new MockAdapter(axios);
  useAuthStore.setState({ user: null, accessToken: null, isInitialized: false });
});

afterEach(() => {
  apiMock.restore();
  axiosMock.restore();
});

// ── Request interceptor ───────────────────────────────────────────────────────

describe('request interceptor', () => {
  it('adds Bearer token when store has an access token', async () => {
    useAuthStore.setState({ accessToken: 'secret' });
    apiMock.onGet('/api/test').reply(200, {});

    await api.get('/api/test');

    expect(apiMock.history.get[0].headers?.Authorization).toBe('Bearer secret');
  });

  it('omits the Authorization header when no token is stored', async () => {
    apiMock.onGet('/api/test').reply(200, {});

    await api.get('/api/test');

    expect(apiMock.history.get[0].headers?.Authorization).toBeUndefined();
  });
});

// ── 401 response interceptor ──────────────────────────────────────────────────

describe('401 response interceptor – successful refresh', () => {
  it('calls refresh, stores new token, and retries the original request', async () => {
    useAuthStore.setState({ accessToken: 'old' });

    // First attempt → 401; retry → 200
    apiMock
      .onGet('/api/notes')
      .replyOnce(401)
      .onGet('/api/notes')
      .reply(200, { items: [] });

    // Refresh via bare axios.post → success
    axiosMock.onPost('/api/auth/refresh').reply(200, { access_token: 'fresh' });

    const res = await api.get('/api/notes');

    expect(res.status).toBe(200);
    expect(useAuthStore.getState().accessToken).toBe('fresh');

    // The retry request should carry the refreshed token
    const retryHeaders = apiMock.history.get[1]?.headers;
    expect(retryHeaders?.Authorization).toBe('Bearer fresh');
  });
});

describe('401 response interceptor – failed refresh', () => {
  beforeEach(() => {
    // Allow us to spy on window.location.href assignments
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { href: '/' },
    });
  });

  it('calls logout and redirects to /auth/login when refresh fails', async () => {
    useAuthStore.setState({ accessToken: 'stale' });

    apiMock.onGet('/api/notes').reply(401);
    axiosMock.onPost('/api/auth/refresh').reply(401); // refresh itself fails

    try {
      await api.get('/api/notes');
    } catch {
      // expected rejection after failed refresh
    }

    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(window.location.href).toBe('/auth/login');
  });

  it('does not call refresh again if the retried request also returns 401', async () => {
    useAuthStore.setState({ accessToken: 'tok' });

    // Both the original and the retry fail with 401
    apiMock
      .onGet('/api/protected')
      .replyOnce(401)
      .onGet('/api/protected')
      .reply(401);

    // Refresh succeeds so a retry is attempted
    axiosMock.onPost('/api/auth/refresh').reply(200, { access_token: 'tok2' });

    try {
      await api.get('/api/protected');
    } catch {
      // second 401 (on retry) propagates as an error
    }

    // Refresh should only have been called once, not twice
    const refreshCalls = axiosMock.history.post.filter(
      (r) => r.url === '/api/auth/refresh',
    );
    expect(refreshCalls).toHaveLength(1);
  });
});

// ── isAxiosError ──────────────────────────────────────────────────────────────

describe('isAxiosError', () => {
  it('returns true for an AxiosError instance', () => {
    expect(isAxiosError(new axios.AxiosError('oops'))).toBe(true);
  });

  it('returns false for a plain Error', () => {
    expect(isAxiosError(new Error('plain'))).toBe(false);
  });

  it('returns false for primitives and null', () => {
    expect(isAxiosError(null)).toBe(false);
    expect(isAxiosError('string')).toBe(false);
    expect(isAxiosError(0)).toBe(false);
  });
});
