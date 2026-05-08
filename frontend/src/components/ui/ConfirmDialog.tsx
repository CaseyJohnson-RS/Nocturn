import { useEffect } from 'react';
import { Button } from './Button';

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  danger,
  loading,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !loading) onCancel();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [loading, onCancel]);

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: 'rgba(0,0,0,0.6)' }}
      onMouseDown={(e) => { if (e.target === e.currentTarget && !loading) onCancel(); }}
    >
      <div
        className="bg-bg-card border border-border rounded-lg flex flex-col overflow-hidden"
        style={{ width: '360px', boxShadow: '0 24px 48px rgba(0,0,0,0.45)' }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-2.5"
          style={{ padding: '16px 20px 14px' }}
        >
          {danger && (
            <div
              className="flex-shrink-0 flex items-center justify-center rounded-full"
              style={{
                width: '30px', height: '30px',
                background: 'rgba(244,71,71,0.12)',
                border: '1px solid rgba(244,71,71,0.25)',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" strokeWidth="2">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                <path d="M10 11v6" /><path d="M14 11v6" />
                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
              </svg>
            </div>
          )}
          <span
            className="text-[14px] font-semibold"
            style={{ color: danger ? 'var(--color-danger)' : 'var(--color-fg)' }}
          >
            {title}
          </span>
        </div>

        <div className="border-t border-border" />

        {/* Body */}
        <div style={{ padding: '14px 20px 20px' }} className="flex flex-col gap-5">
          <p className="text-[13px] leading-relaxed" style={{ color: 'var(--color-fg-muted)' }}>
            {message}
          </p>
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" size="md" style={{ padding: '8px 20px' }} onClick={onCancel} disabled={loading}>
              {cancelLabel}
            </Button>
            <Button
              variant={danger ? 'danger' : 'primary'}
              size="md"
              style={{ padding: '8px 20px' }}
              onClick={onConfirm}
              loading={loading}
            >
              {confirmLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
