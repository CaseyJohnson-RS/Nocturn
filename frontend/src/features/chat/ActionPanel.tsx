import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { aiApi } from '@/api/ai';
import { useChatStore } from '@/stores/chat';
import { ProposalCard } from './ProposalCard';
import { PendingConfirmCard } from './PendingConfirmCard';
import { t } from '@/i18n';
import type { Proposal, PendingConfirmation } from '@/types/api';

interface ActionPanelProps {
  sessionId: string;
}

export function ActionPanel({ sessionId }: ActionPanelProps) {
  const s = t();
  const qc = useQueryClient();
  const { messages, streamingActions, isGenerating } = useChatStore();
  const [open, setOpen] = useState(true);
  const [isProcessingAll, setIsProcessingAll] = useState(false);

  // Collect pending actions from committed messages
  const proposals: Array<{ proposal: Proposal; messageId: string; streaming: boolean }> = [];
  const confirmations: Array<{ confirmation: PendingConfirmation; messageId: string; streaming: boolean }> = [];

  for (const msg of messages) {
    for (const action of msg.actions ?? []) {
      if (action.type === 'proposal' && (action as Proposal).status === 'pending') {
        proposals.push({ proposal: action as Proposal, messageId: msg.id, streaming: false });
      } else if (action.type === 'pending_confirmation' && (action as PendingConfirmation).status === 'pending') {
        confirmations.push({ confirmation: action as PendingConfirmation, messageId: msg.id, streaming: false });
      }
    }
  }

  // Also surface actions arriving in the live stream — shown disabled until committed
  if (isGenerating) {
    for (const action of streamingActions) {
      if (action.type === 'proposal') {
        proposals.push({ proposal: action as Proposal, messageId: 'streaming', streaming: true });
      } else if (action.type === 'pending_confirmation') {
        confirmations.push({ confirmation: action as PendingConfirmation, messageId: 'streaming', streaming: true });
      }
    }
  }

  const pendingCount = proposals.length + confirmations.length;

  // Auto-open whenever new pending items arrive — hook must be before early return
  useEffect(() => {
    if (pendingCount > 0) setOpen(true);
  }, [pendingCount]);

  if (pendingCount === 0) return null;

  const committedProposals = proposals.filter((p) => !p.streaming);

  async function handleAll(status: 'applied' | 'dismissed') {
    if (isProcessingAll) return;
    setIsProcessingAll(true);

    // Optimistic update: mark all targeted proposals immediately so the UI
    // doesn't wait on server timing or getMessages latency.
    const targetIds = new Set(committedProposals.map((p) => p.proposal.id));
    const snapshot = useChatStore.getState().messages;
    useChatStore.getState().setMessages(
      snapshot.map((msg) => ({
        ...msg,
        actions: (msg.actions ?? []).map((action) =>
          action.type === 'proposal' && targetIds.has((action as Proposal).id)
            ? ({ ...action, status } as Proposal)
            : action
        ),
      }))
    );

    try {
      // Group by messageId — sequential within the same message to avoid
      // read-modify-write races on the backend; parallel across messages.
      const byMessage = new Map<string, typeof committedProposals>();
      for (const p of committedProposals) {
        const group = byMessage.get(p.messageId) ?? [];
        group.push(p);
        byMessage.set(p.messageId, group);
      }
      await Promise.allSettled(
        Array.from(byMessage.values()).map(async (group) => {
          for (const { proposal, messageId } of group) {
            await aiApi.updateAction(sessionId, messageId, proposal.id, { status });
          }
        })
      );

      // Authoritative refresh: surfaces any proposals that failed to update
      // (they'll reappear as still-pending).
      try {
        const res = await aiApi.getMessages(sessionId, { limit: 100 });
        useChatStore.getState().setMessages(res.items);
      } catch {
        // getMessages failed — keep optimistic state; user can retry individual cards.
      }

      if (status === 'applied') {
        void qc.invalidateQueries({ queryKey: ['notes'] });
        if (committedProposals.some(({ proposal }) =>
          proposal.proposal_type === 'add_tags' || proposal.proposal_type === 'remove_tags'
        )) {
          void qc.invalidateQueries({ queryKey: ['tags'] });
        }
      }
    } finally {
      setIsProcessingAll(false);
    }
  }

  return (
    <div className="flex-shrink-0 border-t border-border" style={{ background: 'var(--color-bg-tab)' }}>
      {/* Header row */}
      <div
        className="flex items-center justify-between cursor-pointer hover:bg-bg-hover select-none"
        style={{ padding: '5px 12px' }}
        onClick={() => setOpen((v) => !v)}
      >
        {/* Left: chevron + label + count */}
        <div className="flex items-center gap-2">
          <svg
            width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
            style={{ flexShrink: 0, transform: open ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.15s' }}
          >
            <polyline points="6 9 12 15 18 9"/>
          </svg>
          <span className="text-[11px] font-medium text-fg-muted uppercase tracking-wider">
            {s.chat.proposals}
          </span>
          <span
            className="text-fg-link font-semibold bg-accent/20 rounded-full"
            style={{ fontSize: '12px', padding: '1px 7px' }}
          >
            {pendingCount}
          </span>
        </div>

        {/* Right: accept/reject all buttons */}
        {open && committedProposals.length >= 2 && (
          <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
            <button
              className="text-[12px] rounded bg-accent/20 text-fg-link hover:bg-accent/30 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ padding: '3px 10px' }}
              disabled={isProcessingAll}
              onClick={() => void handleAll('applied')}
            >
              ✓ {s.chat.acceptAll}
            </button>
            <button
              className="text-[12px] rounded bg-bg-hover text-fg-muted hover:text-fg disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ padding: '3px 10px' }}
              disabled={isProcessingAll}
              onClick={() => void handleAll('dismissed')}
            >
              ✕ {s.chat.rejectAll}
            </button>
          </div>
        )}
      </div>

      {/* Items */}
      {open && (
        <div className="overflow-y-auto" style={{ maxHeight: '240px', padding: '0 10px 5px' }}>
          {confirmations.map(({ confirmation, streaming }) => (
            <PendingConfirmCard
              key={confirmation.id}
              confirmation={confirmation}
              sessionId={sessionId}
              disabled={streaming}
            />
          ))}
          {proposals.map(({ proposal, messageId, streaming }) => (
            <ProposalCard
              key={proposal.id}
              proposal={proposal}
              sessionId={sessionId}
              messageId={messageId}
              disabled={streaming || isProcessingAll}
            />
          ))}
        </div>
      )}
    </div>
  );
}
