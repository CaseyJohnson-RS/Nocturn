import { createBrowserRouter, Navigate, Outlet } from 'react-router';
import { lazy, Suspense, useEffect } from 'react';
import { useAuthStore } from '@/stores/auth';
import { authApi } from '@/api/auth';

const AppShell = lazy(() => import('@/components/layout/AppShell'));
const LoginPage = lazy(() => import('@/features/auth/LoginPage'));
const RegisterPage = lazy(() => import('@/features/auth/RegisterPage'));
const ConfirmEmailPage = lazy(() => import('@/features/auth/ConfirmEmailPage'));
const ForgotPasswordPage = lazy(() => import('@/features/auth/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('@/features/auth/ResetPasswordPage'));

// Proactive refresh interval — slightly less than the access token TTL (15 min).
// Keeps the session alive without waiting for a 401 to trigger a refresh.
// Also acts as a keep-alive ping for the backend on free-tier hosting.
const PROACTIVE_REFRESH_MS = 12 * 60 * 1000; // 12 minutes

function RootLayout() {
  const { setUser, setAccessToken, setInitialized, isInitialized } = useAuthStore();

  useEffect(() => {
    if (isInitialized) return;
    authApi
      .refresh()
      .then((tok) => { setAccessToken(tok.access_token); return authApi.me(); })
      .then(setUser)
      .catch(() => {})
      .finally(setInitialized);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Start proactive token refresh once the app is initialized.
  // On success: silently update the access token.
  // On failure: ignore — the 401 interceptor in client.ts will handle it when
  //             a real request is made, or the user will be redirected to login.
  useEffect(() => {
    if (!isInitialized) return;

    const id = setInterval(() => {
      if (!useAuthStore.getState().user) return; // not logged in, skip
      authApi
        .refresh()
        .then((tok) => useAuthStore.getState().setAccessToken(tok.access_token))
        .catch(() => { /* silent — natural expiry will be handled by the interceptor */ });
    }, PROACTIVE_REFRESH_MS);

    return () => clearInterval(id);
  }, [isInitialized]);

  return (
    <Suspense fallback={null}>
      <Outlet />
    </Suspense>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const initialized = useAuthStore((s) => s.isInitialized);
  if (!initialized) return null;
  if (!user) return <Navigate to="/auth/login" replace />;
  return <>{children}</>;
}

function RequireGuest({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const initialized = useAuthStore((s) => s.isInitialized);
  if (!initialized) return null;
  if (user) return <Navigate to="/app" replace />;
  return <>{children}</>;
}

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { index: true, element: <Navigate to="/app" replace /> },
      {
        path: '/app',
        element: <RequireAuth><AppShell /></RequireAuth>,
      },
      {
        path: '/auth/login',
        element: <RequireGuest><LoginPage /></RequireGuest>,
      },
      {
        path: '/auth/register',
        element: <RequireGuest><RegisterPage /></RequireGuest>,
      },
      { path: '/auth/confirm-email', element: <ConfirmEmailPage /> },
      {
        path: '/auth/forgot-password',
        element: <RequireGuest><ForgotPasswordPage /></RequireGuest>,
      },
      { path: '/auth/reset-password', element: <ResetPasswordPage /> },
      { path: '*', element: <Navigate to="/app" replace /> },
    ],
  },
]);
