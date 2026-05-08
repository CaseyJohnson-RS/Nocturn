import { useMutation, useQueryClient } from '@tanstack/react-query';
import { aiApi } from '@/api/ai';
import { useUIStore } from '@/stores/ui';
import { useChatStore } from '@/stores/chat';
import { t } from '@/i18n';
import type { Proposal, ProposalType } from '@/types/api';
import type { Strings } from '@/i18n/ru';

function getLabel(type: ProposalType, s: Strings): string {
  const map: Record<ProposalType, string> = {
    edit_note:   s.chat.editNote,
    create_note: s.chat.createNote,
    delete_note: s.chat.deleteNote,
    add_tags:    s.chat.addTags,
    remove_tags: s.chat.removeTags,
  };
  return map[type] ?? type;
}

const TYPE_COLORS: Record<ProposalType, { border: string; bg: string; label: string }> = {
  edit_note:   { border: 'var(--color-accent)',   bg: 'rgba(0, 122, 204, 0.07)',   label: 'var(--color-accent)' },
  create_note: { border: 'var(--color-success)',  bg: 'rgba(78, 201, 176, 0.07)',  label: 'var(--color-success)' },
  delete_note: { border: 'var(--color-danger)',   bg: 'rgba(244, 71, 71, 0.07)',   label: 'var(--color-danger)' },
  add_tags:    { border: 'var(--color-fg-link)',  bg: 'rgba(77, 170, 252, 0.07)',  label: 'var(--color-fg-link)' },
  remove_tags: { border: 'var(--color-warning)',  bg: 'rgba(204, 167, 0, 0.07)',   label: 'var(--color-warning)' },
};

interface ProposalCardProps {
  proposal: Proposal;
  sessionId: string;
  messageId: string;
  disabled?: boolean;
}

export function ProposalCard({ proposal, sessionId, messageId, disabled }: ProposalCardProps) {
  const s = t();
  const qc = useQueryClient();
  const { openTab } = useUIStore();
  const { replaceMessage } = useChatStore();

  const colors = TYPE_COLORS[proposal.proposal_type] ?? TYPE_COLORS.edit_note;

  const actionMut = useMutation({
    mutationFn: (status: 'applied' | 'dismissed') =>
      aiApi.updateAction(sessionId, messageId, proposal.id, { status }),
    onSuccess: (msg, status) => {
      replaceMessage(msg);
      if (status === 'applied') {
        void qc.invalidateQueries({ queryKey: ['notes'] });
        if (proposal.note_id) {
          void qc.invalidateQueries({ queryKey: ['note', proposal.note_id] });
        }
        if (proposal.proposal_type === 'add_tags' || proposal.proposal_type === 'remove_tags') {
          void qc.invalidateQueries({ queryKey: ['tags'] });
        }
      }
    },
  });

  const noteTitle = (proposal.data as { title?: string })?.title
    ?? (proposal.data as { note_title?: string })?.note_title
    ?? s.notes.untitled;

  const isDisabled = disabled || actionMut.isPending;

  return (
    <div
      className="rounded-md border border-border mt-2"
      style={{
        padding: '6px 10px',
        borderLeft: `3px solid ${colors.border}`,
        background: colors.bg,
      }}
    >
      <div className="flex items-start gap-3">
        {/* Left: label + note link */}
        <div className="flex-1 min-w-0">
          <div
            className="text-[10px] font-semibold uppercase tracking-widest mb-1"
            style={{ color: colors.label }}
          >
            {getLabel(proposal.proposal_type, s)}
          </div>
          {proposal.note_id && (
            <div
              className="flex items-center gap-1.5 text-[12px] text-fg-link font-medium cursor-pointer hover:underline truncate"
              onClick={() => proposal.note_id && openTab({ type: 'note', id: proposal.note_id })}
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              {noteTitle}
            </div>
          )}
        </div>

        {/* Right: icon buttons */}
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            className="w-7 h-7 flex items-center justify-center rounded-md text-fg-muted hover:text-success hover:bg-success/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            disabled={isDisabled}
            onClick={() => actionMut.mutate('applied')}
            title={s.chat.accept}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          </button>
          <button
            className="w-7 h-7 flex items-center justify-center rounded-md text-fg-muted hover:text-danger hover:bg-danger/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            disabled={isDisabled}
            onClick={() => actionMut.mutate('dismissed')}
            title={s.chat.reject}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      {proposal.summary && (
        <div className="text-[12px] text-fg-muted leading-relaxed" style={{ marginTop: '3px' }}>
          {proposal.summary}
        </div>
      )}
    </div>
  );
}
