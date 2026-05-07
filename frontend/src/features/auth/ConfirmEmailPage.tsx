import { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router';
import { AuthLayout } from './AuthLayout';
import { authApi } from '@/api/auth';
import { t } from '@/i18n';

type Status = 'loading' | 'success' | 'error';

export default function ConfirmEmailPage() {
  const s = t();
  const [params] = useSearchParams();
  const [status, setStatus] = useState<Status>('loading');

  useEffect(() => {
    const token = params.get('token');
    if (!token) { setStatus('error'); return; }

    authApi
      .confirmEmail({ token })
      .then(() => setStatus('success'))
      .catch(() => setStatus('error'));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AuthLayout title={s.auth.confirmEmail}>
      <div className="flex flex-col items-center gap-4 text-center">
        {status === 'loading' && (
          <span className="inline-block w-6 h-6 border-2 border-border border-t-accent rounded-full animate-spin" />
        )}
        {status === 'success' && (
          <>
            <span className="text-3xl">✅</span>
            <p className="text-[13px] text-fg">{s.auth.emailConfirmed}</p>
            <Link to="/auth/login" className="text-fg-link hover:underline text-[13px]">
              {s.auth.login}
            </Link>
          </>
        )}
        {status === 'error' && (
          <>
            <span className="text-3xl">⚠️</span>
            <p className="text-[13px] text-danger">{s.auth.invalidToken}</p>
            <Link to="/auth/login" className="text-fg-link hover:underline text-[13px]">
              {s.auth.login}
            </Link>
          </>
        )}
      </div>
    </AuthLayout>
  );
}
