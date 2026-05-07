import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi } from 'vitest';
import LoginPage from '@/features/auth/LoginPage';
import { useAuthStore } from '@/stores/auth';
import { authApi } from '@/api/auth';
import { setLocale } from '@/i18n';

// Mock the entire authApi module
vi.mock('@/api/auth', () => ({
  authApi: {
    login: vi.fn(),
    me: vi.fn(),
  },
}));

const mockLogin = vi.mocked(authApi.login);
const mockMe = vi.mocked(authApi.me);

function renderLoginPage() {
  return render(
    <MemoryRouter initialEntries={['/auth/login']}>
      <Routes>
        <Route path="/auth/login" element={<LoginPage />} />
        <Route path="/app" element={<div>App</div>} />
        <Route path="/auth/register" element={<div>Register</div>} />
        <Route path="/auth/forgot-password" element={<div>Forgot</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  setLocale('en');
  vi.clearAllMocks();
  useAuthStore.setState({ user: null, accessToken: null, isInitialized: false });
});

describe('LoginPage', () => {
  it('renders the form fields', () => {
    renderLoginPage();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('renders a link to the register page', () => {
    renderLoginPage();
    expect(screen.getByRole('link', { name: /create account/i })).toBeInTheDocument();
  });

  it('renders a link to forgot password', () => {
    renderLoginPage();
    expect(screen.getByRole('link', { name: /forgot password/i })).toBeInTheDocument();
  });

  it('navigates to /app on successful login', async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValue({ access_token: 'tok-xyz', token_type: 'bearer' });
    mockMe.mockResolvedValue({
      id: 'u1',
      email: 'a@b.com',
      nickname: 'alice',
      role: 'user',
      is_email_confirmed: true,
      is_active: true,
      created_at: '2024-01-01T00:00:00Z',
    });

    renderLoginPage();

    await user.type(screen.getByLabelText(/email/i), 'a@b.com');
    await user.type(screen.getByLabelText(/password/i), 'secret123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('App')).toBeInTheDocument();
    });

    expect(mockLogin).toHaveBeenCalledWith({ email: 'a@b.com', password: 'secret123' });
    expect(useAuthStore.getState().accessToken).toBe('tok-xyz');
  });

  it('shows invalid credentials error on failed login', async () => {
    const user = userEvent.setup();
    const err = Object.assign(new Error('Unauthorized'), {
      isAxiosError: true,
      response: { status: 401, data: {} },
    });
    mockLogin.mockRejectedValue(err);

    renderLoginPage();

    await user.type(screen.getByLabelText(/email/i), 'wrong@test.com');
    await user.type(screen.getByLabelText(/password/i), 'bad');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });
  });

  it('shows blocked account error on 403', async () => {
    const user = userEvent.setup();
    const err = Object.assign(new Error('Forbidden'), {
      isAxiosError: true,
      response: { status: 403, data: {} },
    });
    mockLogin.mockRejectedValue(err);

    renderLoginPage();

    await user.type(screen.getByLabelText(/email/i), 'blocked@test.com');
    await user.type(screen.getByLabelText(/password/i), 'pass');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/blocked/i)).toBeInTheDocument();
    });
  });

  it('submit button is disabled while the request is in flight', async () => {
    const user = userEvent.setup();
    // Never resolves during the test
    mockLogin.mockReturnValue(new Promise(() => {}));

    renderLoginPage();

    await user.type(screen.getByLabelText(/email/i), 'a@b.com');
    await user.type(screen.getByLabelText(/password/i), 'pass');

    // Capture the element reference BEFORE clicking — once loading starts the button
    // replaces its text with an aria-hidden spinner, so name-based queries stop working.
    const submitBtn = screen.getByRole('button', { name: /sign in/i });
    await user.click(submitBtn);

    expect(submitBtn).toBeDisabled();
  });
});
