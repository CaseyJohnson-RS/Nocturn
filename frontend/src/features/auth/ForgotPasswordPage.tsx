import { useState } from 'react';
import { Link } from 'react-router';
import { AuthLayout } from './AuthLayout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { authApi } from '@/api/auth';
import { t } from '@/i18n';

export default function ForgotPasswordPage() {
  const s = t();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await authApi.requestPasswordReset({ email });
      setSent(true);
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <AuthLayout title={s.auth.checkEmail}>
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="text-3xl">📧</span>
          <p className="text-[13px] text-fg-muted leading-relaxed">{s.auth.resetSent}</p>
          <Link to="/auth/login" className="text-fg-link hover:underline text-[13px]">
            ← {s.auth.login}
          </Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={s.auth.resetPassword}>
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
        <Button type="submit" loading={loading} className="w-full">
          {s.auth.sendResetLink}
        </Button>
      </form>
      <p className="text-center text-[12px] text-fg-muted">
        <Link to="/auth/login" className="text-fg-link hover:underline">
          ← {s.auth.login}
        </Link>
      </p>
    </AuthLayout>
  );
}
