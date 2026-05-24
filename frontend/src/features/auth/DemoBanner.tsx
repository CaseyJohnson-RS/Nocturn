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
    <div
      className="rounded-lg border border-border bg-bg-tab"
      style={{ padding: '16px 18px' }}
    >
      {/* Header */}
      <div className="flex items-center gap-2" style={{ marginBottom: '10px' }}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" className="text-fg-muted flex-shrink-0">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <span className="text-[12px] font-medium text-fg-muted">Demo</span>
      </div>

      {/* Hint text */}
      <p className="text-[12px] text-fg-muted leading-relaxed" style={{ marginBottom: '14px' }}>
        {variant === 'register' ? s.auth.demoHintRegister : s.auth.demoHintLogin}
      </p>

      {/* Credentials */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
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
      className="flex items-center rounded hover:bg-bg-hover transition-colors w-full text-left group"
      style={{ padding: '7px 10px', gap: '10px' }}
    >
      <span className="text-fg-disabled flex-shrink-0" style={{ fontSize: '11px', width: '52px' }}>
        {label}
      </span>
      <span className="text-fg font-mono flex-1" style={{ fontSize: '12px' }}>
        {value}
      </span>
      <span
        className="flex-shrink-0 text-right transition-colors"
        style={{
          fontSize: '10px',
          width: '60px',
          color: copied ? 'var(--color-accent)' : undefined,
        }}
      >
        {copied
          ? copiedLabel
          : <span className="text-fg-disabled group-hover:text-fg-muted">&nbsp;copy</span>}
      </span>
    </button>
  );
}
