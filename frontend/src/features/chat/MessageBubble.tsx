import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { useQueryClient } from '@tanstack/react-query';
import { ProposalCard } from './ProposalCard';
import { PendingConfirmCard } from './PendingConfirmCard';
import { useUIStore } from '@/stores/ui';
import { useChatStore } from '@/stores/chat';
import { aiApi } from '@/api/ai';
import { t } from '@/i18n';
import type { AIMessageResponse, Proposal, PendingConfirmation } from '@/types/api';

// Parse [[note:uuid|Title]] inline and render chips
function parseNoteLinks(text: string, openNote: (id: string) => void): React.ReactNode[] {
  const parts = text.split(/(\[\[note:[a-f0-9-]+\|[^\]]+\]\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[\[note:([a-f0-9-]+)\|([^\]]+)\]\]$/);
    if (match) {
      const [, id, title] = match;
      return (
        <span key={i} className="note-link" onClick={() => openNote(id)}>
          📄 {title}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

interface GroupActionsBarProps {
  proposals: Proposal[];
  sessionId: string;
  messageId: string;
}

function GroupActionsBar({ proposals, sessionId, messageId }: GroupActionsBarProps) {
  const s = t();
  const qc = useQueryClient();
  const { replaceMessage } = useChatStore();

  async function handleAll(status: 'applied' | 'dismissed') {
    const pending = proposals.filter((p) => p.status === 'pending');
    let touchedNotes = false;
    let touchedTags = false;
    for (const p of pending) {
      try {
        const msg = await aiApi.updateAction(sessionId, messageId, p.id, { status });
        replaceMessage(msg);
        if (status === 'applied') {
          touchedNotes = true;
          if (p.proposal_type === 'add_tags' || p.proposal_type === 'remove_tags') touchedTags = true;
        }
      } catch { /* continue on partial failures */ }
    }
    if (touchedNotes) void qc.invalidateQueries({ queryKey: ['notes'] });
    if (touchedTags) void qc.invalidateQueries({ queryKey: ['tags'] });
  }

  const pendingCount = proposals.filter((p) => p.status === 'pending').length;

  return (
    <div className="flex gap-2 mb-2 mt-1">
      <button
        onClick={() => void handleAll('applied')}
        className="text-[11px] px-2 py-1 rounded bg-accent/20 text-fg-link hover:bg-accent/30 font-medium"
      >
        ✓ {s.chat.acceptAll} ({pendingCount})
      </button>
      <button
        onClick={() => void handleAll('dismissed')}
        className="text-[11px] px-2 py-1 rounded bg-bg-hover text-fg-muted hover:text-fg"
      >
        ✕ {s.chat.rejectAll}
      </button>
    </div>
  );
}

interface MessageBubbleProps {
  message: AIMessageResponse;
  sessionId: string;
  isStreaming?: boolean;
  streamingContent?: string;
}

export function MessageBubble({ message, sessionId, isStreaming, streamingContent }: MessageBubbleProps) {
  const s = t();
  const { openTab } = useUIStore();
  const isUser = message.role === 'user';

  const proposals = (message.actions ?? []).filter(
    (a): a is Proposal => a.type === 'proposal',
  );
  const confirmations = (message.actions ?? []).filter(
    (a): a is PendingConfirmation => a.type === 'pending_confirmation',
  );

  const pendingProposals = proposals.filter((p) => p.status === 'pending');
  const content = isStreaming ? (streamingContent ?? '') : message.content;

  return (
    <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
      <span className="text-[11px] text-fg-muted px-1">
        {isUser ? s.chat.you : s.chat.assistant}
      </span>

      <div
        className={`max-w-[88%] px-3 py-2 rounded-lg text-[13px] leading-relaxed
          ${isUser
            ? 'bg-bg-selected rounded-br-sm'
            : 'bg-bg-card border border-border rounded-bl-sm w-full'
          }`}
      >
        {isUser ? (
          <>{parseNoteLinks(content, (id) => openTab({ type: 'note', id }))}</>
        ) : (
          <div className="md-content">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
            >
              {content + (isStreaming ? ' ▋' : '')}
            </ReactMarkdown>
          </div>
        )}

        {/* Group actions bar (≥2 pending proposals) */}
        {pendingProposals.length >= 2 && (
          <GroupActionsBar
            proposals={proposals}
            sessionId={sessionId}
            messageId={message.id}
          />
        )}

        {/* Individual proposals */}
        {proposals.map((p) => (
          <ProposalCard key={p.id} proposal={p} sessionId={sessionId} messageId={message.id} />
        ))}

        {/* Pending confirmations */}
        {confirmations.map((c) => (
          <PendingConfirmCard key={c.id} confirmation={c} sessionId={sessionId} messageId={message.id} />
        ))}
      </div>
    </div>
  );
}
