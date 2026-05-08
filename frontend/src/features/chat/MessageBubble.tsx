import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { useEffect, useRef, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { useUIStore } from '@/stores/ui';
import { t } from '@/i18n';
import type { AIMessageResponse } from '@/types/api';

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

function preprocessNoteLinks(text: string): string {
  return text.replace(/\[\[note:([a-f0-9-]+)\|([^\]]+)\]\]/gi, '[$2](note:$1)');
}

interface MessageBubbleProps {
  message: AIMessageResponse;
  isStreaming?: boolean;
  streamingContent?: string;
}

const MAX_CHARS_PER_SEC = 90;

export function MessageBubble({ message, isStreaming, streamingContent }: MessageBubbleProps) {
  const s = t();
  const { openTab } = useUIStore();
  const isUser = message.role === 'user';

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
      </div>
    </div>
  );
}
