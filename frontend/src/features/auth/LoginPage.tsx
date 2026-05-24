import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { AuthLayout } from './AuthLayout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/stores/auth';
import { isAxiosError } from '@/api/client';
import { t } from '@/i18n';
import { DemoBanner } from './DemoBanner';

export default function LoginPage() {
  const s = t();
  const navigate = useNavigate();
  const { setUser, setAccessToken } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const tok = await authApi.login({ email, password });
      setAccessToken(tok.access_token);
      const me = await authApi.me();
      setUser(me);
      navigate('/app', { replace: true });
    } catch (err) {
      if (isAxiosError(err)) {
        const status = err.response?.status;
        const code = (err.response?.data as { detail?: string })?.detail;
        if (status === 403 || code === 'account_blocked') {
          setError(s.auth.accountBlocked);
        } else {
          setError(s.auth.invalidCredentials);
        }
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout title="Nocturn" subtitle={s.auth.login}>
      <DemoBanner variant="login" />
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          id="email"
          label={s.auth.email}
          type="email"
          autoComplete="email"
          placeholder={s.auth.emailPlaceholder}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <div className="flex flex-col gap-1">
          <Input
            id="password"
            label={s.auth.password}
            type="password"
            autoComplete="current-password"
            placeholder={s.auth.passwordPlaceholder}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Link
            to="/auth/forgot-password"
            className="text-[11px] text-fg-muted hover:text-fg-link self-end"
          >
            {s.auth.forgotPassword}
          </Link>
        </div>

        {error && (
          <p className="text-[12px] text-danger bg-danger/10 border border-danger/30 rounded px-3 py-2">
            {error}
          </p>
        )}

        <Button type="submit" loading={loading} className="w-full">
          {s.auth.login}
        </Button>
      </form>

      <p className="text-center text-[12px] text-fg-muted">
        {s.auth.noAccount}{' '}
        <Link to="/auth/register" className="text-fg-link hover:underline">
          {s.auth.register}
        </Link>
      </p>
    </AuthLayout>
  );
}
