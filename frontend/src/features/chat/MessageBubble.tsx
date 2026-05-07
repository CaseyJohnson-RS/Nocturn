import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { ProposalCard } from './ProposalCard';
import { PendingConfirmCard } from './PendingConfirmCard';
import { useUIStore } from '@/stores/ui';
import { useChatStore } from '@/stores/chat';
import { aiApi } from '@/api/ai';
import { t } from '@/i18n';
import type { AIMessageResponse, Proposal, PendingConfirmation } from '@/types/api';

const noteLinkStyle: CSSProperties = {
  color: '#4ec9b0',
  background: 'rgba(78, 201, 176, 0.1)',
  border: '1px solid rgba(78, 201, 176, 0.3)',
  borderRadius: '3px',
  padding: '3px 10px',
  cursor: 'pointer',
  fontSize: '0.9em',
  fontWeight: 500,
  whiteSpace: 'nowrap',
  display: 'inline',
};

// For user messages: parse [[note:uuid|Title]] into clickable chips
function parseNoteLinks(text: string, openNote: (id: string) => void): ReactNode[] {
  const parts = text.split(/(\[\[note:[a-f0-9-]+\|[^\]]+\]\])/gi);
  return parts.map((part, i) => {
    const match = part.match(/^\[\[note:([a-f0-9-]+)\|([^\]]+)\]\]$/i);
    if (match) {
      const [, id, title] = match;
      return (
        <span key={i} className="note-link" style={noteLinkStyle} onClick={() => openNote(id)}>
          {title}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

// For markdown: convert [[note:uuid|Title]] → [Title](note:uuid) so ReactMarkdown can handle it
function preprocessNoteLinks(text: string): string {
  return text.replace(/\[\[note:([a-f0-9-]+)\|([^\]]+)\]\]/gi, '[$2](note:$1)');
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

const MAX_CHARS_PER_SEC = 90;

export function MessageBubble({ message, sessionId, isStreaming, streamingContent }: MessageBubbleProps) {
  const s = t();
  const { openTab } = useUIStore();
  const isUser = message.role === 'user';

  // rAF-driven character accumulation: smooth fixed-speed reveal into React state
  const [displayedContent, setDisplayedContent] = useState('');
  const targetRef = useRef('');
  const posRef = useRef(0);
  const lastTsRef = useRef(0);
  const charsOwedRef = useRef(0);

  useEffect(() => {
    targetRef.current = streamingContent ?? '';
  }, [streamingContent]);

  useEffect(() => {
    if (!isStreaming) return;
    targetRef.current = '';
    posRef.current = 0;
    charsOwedRef.current = 0;
    lastTsRef.current = 0;
    setDisplayedContent('');

    let rafId: number;
    const tick = (ts: number) => {
      if (lastTsRef.current === 0) lastTsRef.current = ts;
      const elapsed = ts - lastTsRef.current;
      lastTsRef.current = ts;

      const target = targetRef.current;
      const remaining = target.length - posRef.current;

      if (remaining > 0) {
        charsOwedRef.current += elapsed * MAX_CHARS_PER_SEC / 1000;
        const toWrite = Math.min(Math.floor(charsOwedRef.current), remaining);
        if (toWrite > 0) {
          posRef.current += toWrite;
          charsOwedRef.current -= toWrite;
          setDisplayedContent(target.slice(0, posRef.current));
        }
      } else {
        charsOwedRef.current = 0;
      }

      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [isStreaming]); // eslint-disable-line react-hooks/exhaustive-deps

  const proposals = (message.actions ?? []).filter(
    (a): a is Proposal => a.type === 'proposal',
  );
  const confirmations = (message.actions ?? []).filter(
    (a): a is PendingConfirmation => a.type === 'pending_confirmation',
  );

  const pendingProposals = proposals.filter((p) => p.status === 'pending');
  const content = message.content;

  function renderMarkdown(text: string) {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        urlTransform={(url) => url.startsWith('note:') ? url : defaultUrlTransform(url)}
        components={{
          a({ href, children }) {
            if (href?.startsWith('note:')) {
              const id = href.slice(5);
              return (
                <span className="note-link" style={noteLinkStyle} onClick={() => openTab({ type: 'note', id })}>
                  {children}
                </span>
              );
            }
            return <a href={href}>{children}</a>;
          },
        }}
      >
        {preprocessNoteLinks(text)}
      </ReactMarkdown>
    );
  }

  return (
    <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
      <span className="text-[11px] text-fg-muted px-1">
        {isUser ? s.chat.you : s.chat.assistant}
      </span>

      <div
        className={`max-w-[88%] rounded-lg text-[13px] leading-relaxed
          ${isUser
            ? 'bg-bg-selected rounded-br-sm'
            : 'bg-bg-card border border-border rounded-bl-sm w-full'
          }`}
        style={{ padding: '10px 14px' }}
      >
        {isUser ? (
          <>{parseNoteLinks(content, (id) => openTab({ type: 'note', id }))}</>
        ) : isStreaming ? (
          <div className="streaming-bubble md-content">
            {renderMarkdown(displayedContent)}
            <span className="streaming-cursor" />
          </div>
        ) : (
          <div className="md-content">
            {renderMarkdown(content)}
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
