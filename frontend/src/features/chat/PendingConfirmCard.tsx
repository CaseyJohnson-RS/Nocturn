import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { aiApi, confirmBulkStream } from '@/api/ai';
import { useChatStore } from '@/stores/chat';
import { Button } from '@/components/ui/Button';
import { t } from '@/i18n';
import type { PendingConfirmation } from '@/types/api';

interface PendingConfirmCardProps {
  confirmation: PendingConfirmation;
  sessionId: string;
  messageId: string;
}

export function PendingConfirmCard({ confirmation, sessionId }: PendingConfirmCardProps) {
  const s = t();
  const qc = useQueryClient();
  const [streaming, setStreaming] = useState(false);

  const dismissed = confirmation.status !== 'pending';

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
      // 409 = already confirmed (double-click); other errors logged
      console.error('Confirm bulk error', err);
    } finally {
      // Always refresh from server — gets updated confirmation status + new proposals
      try {
        const res = await aiApi.getMessages(sessionId, { limit: 100 });
        useChatStore.getState().setMessages(res.items);
      } catch { /* keep existing messages on network failure */ }
      // Invalidate every note touched by the bulk op so editors show fresh content
      for (const id of confirmation.note_ids) {
        void qc.invalidateQueries({ queryKey: ['note', id] });
      }
      void qc.invalidateQueries({ queryKey: ['notes'] });
      void qc.invalidateQueries({ queryKey: ['tags'] });
      setStreaming(false);
    }
  }

  return (
    <div className={`rounded-md border-l-[3px] border-warning px-3 py-2.5 mt-2 text-[12px] bg-bg-card border border-border ${dismissed ? 'opacity-60' : ''}`}>
      <div className="flex items-center gap-1 text-[11px] text-fg-muted mb-1">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
          <polyline points="1 4 1 10 7 10"/>
          <path d="M3.51 15a9 9 0 1 0 .49-3.86"/>
        </svg>
        {s.chat.bulkOp} · {s.chat.bulkNotes.replace('{count}', String(confirmation.note_ids.length))}
      </div>
      <div className="text-fg mb-2">{confirmation.summary}</div>

      {!dismissed && (
        <div className="flex gap-1.5">
          <Button
            size="sm"
            onClick={() => void handleConfirm()}
            loading={streaming}
          >
            {s.chat.confirm}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => dismissMut.mutate()}
            disabled={streaming || dismissMut.isPending}
          >
            {s.chat.reject}
          </Button>
        </div>
      )}

      {confirmation.status === 'confirmed' && (
        <div className="text-[11px] text-success">✓ {s.chat.confirmed}</div>
      )}
      {confirmation.status === 'dismissed' && (
        <div className="text-[11px] text-fg-disabled">— {s.chat.dismissed}</div>
      )}
    </div>
  );
}
