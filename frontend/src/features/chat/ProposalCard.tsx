import { useMutation, useQueryClient } from '@tanstack/react-query';
import { aiApi } from '@/api/ai';
import { useUIStore } from '@/stores/ui';
import { useChatStore } from '@/stores/chat';
import { Button } from '@/components/ui/Button';
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

interface ProposalCardProps {
  proposal: Proposal;
  sessionId: string;
  messageId: string;
}

export function ProposalCard({ proposal, sessionId, messageId }: ProposalCardProps) {
  const s = t();
  const qc = useQueryClient();
  const { openTab } = useUIStore();
  const { replaceMessage } = useChatStore();

  const isPending = proposal.status === 'pending';

  const actionMut = useMutation({
    mutationFn: (status: 'applied' | 'dismissed') =>
      aiApi.updateAction(sessionId, messageId, proposal.id, { status }),
    onSuccess: (msg) => {
      replaceMessage(msg);
      void qc.invalidateQueries({ queryKey: ['notes'] });
      if (proposal.note_id) {
        void qc.invalidateQueries({ queryKey: ['note', proposal.note_id] });
      }
      if (proposal.proposal_type === 'add_tags' || proposal.proposal_type === 'remove_tags') {
        void qc.invalidateQueries({ queryKey: ['tags'] });
      }
    },
  });

  const noteTitle = (proposal.data as { title?: string })?.title
    ?? (proposal.data as { note_title?: string })?.note_title
    ?? s.notes.untitled;

  return (
    <div
      className={`rounded-md border-l-[3px] px-3 py-2.5 mt-2 text-[12px]
        ${proposal.status === 'applied'
          ? 'border-success bg-success/5 opacity-70'
          : proposal.status === 'dismissed'
            ? 'border-border bg-bg-card opacity-50'
            : 'border-accent bg-bg-card border border-border'
        }`}
    >
      {/* Type label */}
      <div className="text-[11px] text-fg-muted mb-1">{getLabel(proposal.proposal_type, s)}</div>

      {/* Note link */}
      {proposal.note_id && (
        <div
          className="flex items-center gap-1 text-fg-link font-medium cursor-pointer hover:underline mb-1 truncate"
          onClick={() => proposal.note_id && openTab({ type: 'note', id: proposal.note_id })}
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          {noteTitle}
        </div>
      )}

      {/* Summary */}
      {proposal.summary && (
        <div className="text-fg-muted mb-2">{proposal.summary}</div>
      )}

      {/* Actions */}
      {isPending && (
        <div className="flex gap-1.5">
          <Button
            size="sm"
            onClick={() => actionMut.mutate('applied')}
            loading={actionMut.isPending}
          >
            {s.chat.accept}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => actionMut.mutate('dismissed')}
            disabled={actionMut.isPending}
          >
            {s.chat.reject}
          </Button>
        </div>
      )}

      {/* Final state */}
      {proposal.status === 'applied' && (
        <div className="text-[11px] text-success">✓ {s.chat.applied}</div>
      )}
      {proposal.status === 'dismissed' && (
        <div className="text-[11px] text-fg-disabled">— {s.chat.dismissed}</div>
      )}
    </div>
  );
}
