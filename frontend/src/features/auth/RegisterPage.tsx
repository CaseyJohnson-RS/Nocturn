import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { AuthLayout } from './AuthLayout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { authApi } from '@/api/auth';
import { isAxiosError } from '@/api/client';
import { t } from '@/i18n';

export default function RegisterPage() {
  const s = t();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [nickname, setNickname] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authApi.register({ email, password, nickname });
      navigate('/auth/login', {
        state: { message: s.auth.confirmSent },
        replace: true,
      });
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 409) {
        setError(s.auth.emailTaken);
      } else {
        setError(s.common.error);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout title={s.auth.register}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          id="nickname"
          label={s.auth.nickname}
          type="text"
          autoComplete="username"
          placeholder={s.auth.nicknamePlaceholder}
          value={nickname}
          onChange={(e) => setNickname(e.target.value)}
          required
          minLength={2}
          maxLength={32}
        />
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
        <Input
          id="password"
          label={s.auth.password}
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
          {s.auth.register}
        </Button>
      </form>

      <p className="text-center text-[12px] text-fg-muted">
        {s.auth.hasAccount}{' '}
        <Link to="/auth/login" className="text-fg-link hover:underline">
          {s.auth.login}
        </Link>
      </p>
    </AuthLayout>
  );
}
