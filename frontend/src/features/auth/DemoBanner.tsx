import { useState } from 'react';
import { t } from '@/i18n';

const DEMO_EMAIL = 'admin@example.com';
const DEMO_PASSWORD = 'ChangeMe123';

interface DemoBannerProps {
  variant: 'login' | 'register';
}

export function DemoBanner({ variant }: DemoBannerProps) {
  const s = t();
  const [copied, setCopied] = useState<'email' | 'password' | null>(null);

  function copy(field: 'email' | 'password') {
    const value = field === 'email' ? DEMO_EMAIL : DEMO_PASSWORD;
    void navigator.clipboard.writeText(value).then(() => {
      setCopied(field);
      setTimeout(() => setCopied(null), 1500);
    });
  }

  return (
    <div className="rounded-lg border border-border bg-bg-tab px-4 py-3 flex flex-col gap-2.5">
      <p className="text-[12px] text-fg-muted leading-relaxed">
        {variant === 'register' ? s.auth.demoHintRegister : s.auth.demoHintLogin}
      </p>

      <div className="flex flex-col gap-1">
        <CredRow
          label={s.auth.email}
          value={DEMO_EMAIL}
          copied={copied === 'email'}
          copiedLabel={s.auth.demoCopied}
          onClick={() => copy('email')}
        />
        <CredRow
          label={s.auth.password}
          value={DEMO_PASSWORD}
          copied={copied === 'password'}
          copiedLabel={s.auth.demoCopied}
          onClick={() => copy('password')}
        />
      </div>
    </div>
  );
}

function CredRow({
  label,
  value,
  copied,
  copiedLabel,
  onClick,
}: {
  label: string;
  value: string;
  copied: boolean;
  copiedLabel: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center justify-between gap-2 rounded px-2 py-1 hover:bg-bg-hover transition-colors w-full text-left group"
    >
      <span className="text-[11px] text-fg-disabled w-14 flex-shrink-0">{label}</span>
      <span className="text-[12px] text-fg font-mono flex-1">{value}</span>
      <span className="text-[10px] text-fg-disabled group-hover:text-fg-muted flex-shrink-0 w-14 text-right">
        {copied ? copiedLabel : '⌘C'}
      </span>
    </button>
  );
}
