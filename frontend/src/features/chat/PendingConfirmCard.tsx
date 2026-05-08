import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { aiApi, confirmBulkStream } from '@/api/ai';
import { useChatStore } from '@/stores/chat';
import { t } from '@/i18n';
import type { PendingConfirmation } from '@/types/api';

interface PendingConfirmCardProps {
  confirmation: PendingConfirmation;
  sessionId: string;
  disabled?: boolean;
}

export function PendingConfirmCard({ confirmation, sessionId, disabled }: PendingConfirmCardProps) {
  const s = t();
  const qc = useQueryClient();
  const [streaming, setStreaming] = useState(false);

  const dismissMut = useMutation({
    mutationFn: () => aiApi.dismissBulk(sessionId, confirmation.id),
    onSuccess: () => {
      aiApi.getMessages(sessionId, { limit: 100 }).then((res) => {
        useChatStore.getState().setMessages(res.items);
      });
    },
  });

  async function handleConfirm() {
    setStreaming(true);
    try {
      const gen = confirmBulkStream(sessionId, confirmation.id);
      for await (const _ of gen) { /* drain the stream */ }
    } catch (err: unknown) {
      console.error('Confirm bulk error', err);
    } finally {
      try {
        const res = await aiApi.getMessages(sessionId, { limit: 100 });
        useChatStore.getState().setMessages(res.items);
      } catch { /* keep existing messages on network failure */ }
      for (const id of confirmation.note_ids) {
        void qc.invalidateQueries({ queryKey: ['note', id] });
      }
      void qc.invalidateQueries({ queryKey: ['notes'] });
      void qc.invalidateQueries({ queryKey: ['tags'] });
      setStreaming(false);
    }
  }

  const isDisabled = disabled || streaming || dismissMut.isPending;

  return (
    <div
      className="rounded-md border border-border mt-2"
      style={{ padding: '6px 10px', borderLeft: '3px solid var(--color-warning)', background: 'rgba(204, 167, 0, 0.07)' }}
    >
      {/* Top row: label + note count + action buttons */}
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-[10px] font-semibold text-fg-muted uppercase tracking-widest mb-1">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 .49-3.86"/>
            </svg>
            {s.chat.bulkOp}
            <span className="text-fg-disabled normal-case tracking-normal font-normal">
              · {s.chat.bulkNotes.replace('{count}', String(confirmation.note_ids.length))}
            </span>
          </div>
        </div>

        {/* Icon buttons */}
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            className="w-7 h-7 flex items-center justify-center rounded-md text-fg-muted hover:text-success hover:bg-success/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            disabled={isDisabled}
            onClick={() => void handleConfirm()}
            title={s.chat.confirm}
          >
            {streaming ? (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="animate-spin">
                <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            )}
          </button>
          <button
            className="w-7 h-7 flex items-center justify-center rounded-md text-fg-muted hover:text-danger hover:bg-danger/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            disabled={isDisabled}
            onClick={() => dismissMut.mutate()}
            title={s.chat.reject}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="text-[12px] text-fg leading-relaxed" style={{ marginTop: '2px' }}>
        {confirmation.summary}
      </div>
    </div>
  );
}
