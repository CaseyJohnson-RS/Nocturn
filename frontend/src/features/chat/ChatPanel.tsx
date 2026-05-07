import { useEffect, useRef, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { aiApi, sendMessage } from '@/api/ai';
import { useChatStore } from '@/stores/chat';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';
import { t } from '@/i18n';
import type { AIMessageResponse, Action, Proposal, PendingConfirmation } from '@/types/api';

export default function ChatPanel() {
  const s = t();
  const {
    activeSessionId, messages, isGenerating, streamingContent, streamingActions,
    setActiveSession, setMessages, addMessage, setGenerating, appendDelta,
    pushStreamingAction, clearStreaming, cancel,
  } = useChatStore();

  const msgsEndRef = useRef<HTMLDivElement>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  // ── Sessions list ──────────────────────────────────────────────────────────
  const { data: sessionsData, refetch: refetchSessions } = useQuery({
    queryKey: ['ai-sessions'],
    queryFn: () => aiApi.listSessions({ limit: 50 }),
  });
  const sessions = sessionsData?.items ?? [];

  // ── Create initial session on mount ───────────────────────────────────────
  const createSessionMut = useMutation({
    mutationFn: (dismissId?: string) =>
      aiApi.createSession({ dismiss_session_id: dismissId ?? null }),
    onSuccess: (session) => {
      setActiveSession(session.id);
      void refetchSessions();
    },
  });

  useEffect(() => {
    if (!activeSessionId && sessions.length > 0) {
      setActiveSession(sessions[0].id);
    } else if (!activeSessionId && sessions.length === 0) {
      createSessionMut.mutate(undefined);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Load messages when session changes ────────────────────────────────────
  useEffect(() => {
    if (!activeSessionId) return;
    aiApi.getMessages(activeSessionId, { limit: 100 }).then((res) => {
      setMessages(res.items);
    });
  }, [activeSessionId, setMessages]);

  // ── Auto-scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    msgsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, streamingContent]);

  // ── Has pending proposals (blocks input) ──────────────────────────────────
  const hasPending = messages.filter(Boolean).some((m) =>
    (m.actions ?? []).some(
      (a) => a.type === 'proposal'
        ? (a as Proposal).status === 'pending'
        : (a as PendingConfirmation).status === 'pending',
    ),
  );

  // ── Send message ──────────────────────────────────────────────────────────
  async function handleSend(content: string, attachedNoteIds: string[]) {
    if (!activeSessionId || isGenerating) return;

    const controller = new AbortController();
    setGenerating(true, controller);

    // Optimistic user message
    const optimistic: AIMessageResponse = {
      id: `opt-${Date.now()}`,
      session_id: activeSessionId,
      role: 'user',
      content,
      actions: null,
      attached_note_ids: attachedNoteIds.length ? attachedNoteIds : null,
      created_at: new Date().toISOString(),
    };
    addMessage(optimistic);

    try {
      const gen = sendMessage(
        activeSessionId,
        { content, attached_note_ids: attachedNoteIds },
        controller.signal,
      );

      for await (const frame of gen) {
        switch (frame.event) {
          case 'ai:text_delta':
            appendDelta((frame.data as { delta: string }).delta);
            // Yield a macrotask so React can flush and the browser can paint
            // before the next token — this makes streaming visually progressive
            // even when the server delivers multiple tokens in one TCP chunk.
            await new Promise<void>((resolve) => setTimeout(resolve, 0));
            break;
          case 'ai:proposal':
            pushStreamingAction(frame.data as Action);
            break;
          case 'ai:pending_confirmation':
            pushStreamingAction(frame.data as Action);
            break;
          case 'ai:done': {
            // Fetch the authoritative message list so we always show server state,
            // regardless of what the ai:done payload contains.  The streaming
            // overlay stays visible during the fetch, then disappears once messages
            // are loaded — no flash, no stale-closure issues.
            try {
              const res = await aiApi.getMessages(activeSessionId!, { limit: 100 });
              setMessages(res.items);
            } catch {
              // On error keep whatever messages we have
            }
            clearStreaming();
            void refetchSessions(); // update title in session list
            break;
          }
          case 'ai:error':
            console.error('AI error', frame.data);
            clearStreaming();
            break;
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        console.error('SSE error', err);
      }
      clearStreaming();
    } finally {
      setGenerating(false);
    }
  }

  function handleStop() {
    cancel();
    if (activeSessionId) void aiApi.cancelGeneration(activeSessionId);
  }

  // ── Session management ────────────────────────────────────────────────────
  const deleteSessionMut = useMutation({
    mutationFn: (id: string) => aiApi.deleteSession(id),
    onSuccess: (_, id) => {
      void refetchSessions();
      if (activeSessionId === id) {
        setActiveSession(null);
        createSessionMut.mutate(undefined);
      }
    },
  });

  const renameSessionMut = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      aiApi.updateSession(id, { title }),
    onSuccess: () => { void refetchSessions(); setRenamingId(null); },
  });

  function commitRename(id: string) {
    if (renameValue.trim()) renameSessionMut.mutate({ id, title: renameValue.trim() });
    else setRenamingId(null);
  }

  const activeSession = sessions.find((s2) => s2.id === activeSessionId);

  // Build streaming message (shown while generating)
  const streamingMsg: AIMessageResponse | null = isGenerating
    ? {
        id: 'streaming',
        session_id: activeSessionId ?? '',
        role: 'assistant',
        content: streamingContent,
        actions: streamingActions.length ? streamingActions : null,
        attached_note_ids: null,
        created_at: new Date().toISOString(),
      }
    : null;

  return (
    <aside
      className="flex flex-col flex-shrink-0 border-l border-border overflow-hidden"
      style={{ width: 'var(--chat-w)', background: 'var(--color-bg-base)' }}
    >
      {/* Header */}
      <div
        className="flex-shrink-0 flex items-center justify-between px-3 border-b border-border relative"
        style={{ height: 'var(--tabbar-h)', background: 'var(--color-bg-tab)' }}
      >
        <button
          className="flex items-center gap-1.5 text-[12px] font-medium text-fg-muted hover:text-fg"
          onClick={() => setHistoryOpen((v) => !v)}
        >
          💬 {activeSession?.title ?? s.chat.chat}
          <span className="text-[10px]">▾</span>
        </button>
        <button
          className="text-[12px] text-fg-muted hover:text-fg px-1.5 py-0.5 rounded hover:bg-bg-hover"
          title={s.chat.newChat}
          onClick={() => createSessionMut.mutate(activeSessionId ?? undefined)}
        >
          +
        </button>

        {/* Session history dropdown */}
        {historyOpen && (
          <div className="absolute top-full right-1 w-72 bg-bg-card border border-border rounded-md z-30 shadow-xl overflow-hidden"
            style={{ top: 'calc(100% + 2px)' }}
          >
            {sessions.length === 0 && (
              <div className="px-3 py-4 text-[12px] text-fg-muted text-center">
                {s.chat.noSessions}
              </div>
            )}
            {sessions.map((sess) => (
              <div
                key={sess.id}
                className={`flex items-center gap-2 px-3 py-2 border-b border-border cursor-pointer hover:bg-bg-hover
                  ${sess.id === activeSessionId ? 'bg-bg-selected/30' : ''}`}
              >
                {renamingId === sess.id ? (
                  <input
                    autoFocus
                    className="flex-1 bg-bg-input border border-border-focus rounded px-1.5 py-0.5 text-[12px] text-fg outline-none"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => commitRename(sess.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') commitRename(sess.id);
                      if (e.key === 'Escape') setRenamingId(null);
                    }}
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <span
                    className="flex-1 text-[12px] truncate"
                    onClick={() => { setActiveSession(sess.id); setHistoryOpen(false); }}
                  >
                    {sess.title ?? s.chat.chat}
                  </span>
                )}
                <span className="text-[11px] text-fg-muted flex-shrink-0">
                  {sess.last_message_at
                    ? new Date(sess.last_message_at).toLocaleDateString([], { day: 'numeric', month: 'short' })
                    : ''}
                </span>
                <button
                  className="flex-shrink-0 w-5 h-5 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-bg-hover text-[14px]"
                  onClick={(e) => {
                    e.stopPropagation();
                    setRenamingId(sess.id);
                    setRenameValue(sess.title ?? '');
                  }}
                >
                  ✏
                </button>
                <button
                  className="flex-shrink-0 w-5 h-5 flex items-center justify-center text-fg-muted hover:text-danger rounded hover:bg-danger/10 text-[14px]"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(s.chat.deleteSessionConfirm.replace('{title}', sess.title ?? s.chat.chat))) {
                      deleteSessionMut.mutate(sess.id);
                    }
                  }}
                >
                  🗑
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-3">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            sessionId={activeSessionId ?? ''}
          />
        ))}

        {/* Streaming assistant message */}
        {streamingMsg && (
          <MessageBubble
            message={streamingMsg}
            sessionId={activeSessionId ?? ''}
            isStreaming
            streamingContent={streamingContent}
          />
        )}

        {/* Thinking indicator */}
        {isGenerating && !streamingContent && (
          <div className="flex flex-col gap-1 items-start">
            <span className="text-[11px] text-fg-muted px-1">{s.chat.assistant}</span>
            <div className="flex items-center gap-1.5 px-3 py-2 bg-bg-card border border-border rounded-lg text-[12px] text-fg-muted">
              <span className="animate-bounce" style={{ animationDelay: '0ms' }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: '150ms' }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: '300ms' }}>●</span>
              <span className="ml-1">{s.chat.thinking}</span>
            </div>
          </div>
        )}

        <div ref={msgsEndRef} />
      </div>

      {/* Pending proposals hint */}
      {hasPending && !isGenerating && (
        <div className="flex-shrink-0 px-3 py-2 bg-bg-card border-t border-border text-[11px] text-warning text-center">
          ⚠ {s.chat.pendingHint}
        </div>
      )}

      {/* Input */}
      <ChatInput
        onSend={(content, ids) => void handleSend(content, ids)}
        disabled={hasPending}
        onStop={handleStop}
      />
    </aside>
  );
}
