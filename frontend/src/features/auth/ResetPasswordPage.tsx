import { useState } from 'react';
import { useSearchParams, Link } from 'react-router';
import { AuthLayout } from './AuthLayout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { authApi } from '@/api/auth';
import { isAxiosError } from '@/api/client';
import { t } from '@/i18n';

export default function ResetPasswordPage() {
  const s = t();
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authApi.resetPassword({ token, new_password: password });
      setDone(true);
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 400) {
        setError(s.auth.invalidToken);
      } else {
        setError(s.common.error);
      }
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <AuthLayout title={s.auth.resetPassword}>
        <p className="text-center text-[13px] text-danger">{s.auth.invalidToken}</p>
      </AuthLayout>
    );
  }

  if (done) {
    return (
      <AuthLayout title={s.auth.resetPassword}>
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="text-3xl">✅</span>
          <p className="text-[13px] text-fg">{s.auth.passwordChanged}</p>
          <Link to="/auth/login" className="text-fg-link hover:underline text-[13px]">
            {s.auth.login}
          </Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={s.auth.resetPassword}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          id="password"
          label={s.auth.newPassword}
          type="password"
          autoComplete="new-password"
          placeholder={s.auth.passwordPlaceholder}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          maxLength={128}
        />

        {error && (
          <p className="text-[12px] text-danger bg-danger/10 border border-danger/30 rounded px-3 py-2">
            {error}
          </p>
        )}

        <Button type="submit" loading={loading} className="w-full">
          {s.auth.resetPassword}
        </Button>
      </form>
    </AuthLayout>
  );
}
