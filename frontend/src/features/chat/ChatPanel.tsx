import { useEffect, useRef, useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiApi, sendMessage } from '@/api/ai';
import { useChatStore } from '@/stores/chat';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';
import { t } from '@/i18n';
import type { AIMessageResponse, Action, Proposal, PendingConfirmation, SessionResponse } from '@/types/api';

export default function ChatPanel() {
  const s = t();
  const queryClient = useQueryClient();
  const {
    activeSessionId, messages, isGenerating, streamingContent, streamingActions,
    setActiveSession, setMessages, addMessage, setGenerating, appendDelta,
    pushStreamingAction, clearStreaming, cancel,
  } = useChatStore();

  const msgsEndRef = useRef<HTMLDivElement>(null);
  const skipNextLoadRef = useRef(false);
  const historyRef = useRef<HTMLDivElement>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [menuPos, setMenuPos] = useState<{ top: number; right: number } | null>(null);

  // ── Sessions list ──────────────────────────────────────────────────────────
  const { data: sessionsData, refetch: refetchSessions } = useQuery({
    queryKey: ['ai-sessions'],
    queryFn: () => aiApi.listSessions({ limit: 50 }),
  });
  const sessions = sessionsData?.items ?? [];

  // ── Activate most-recent session once the list loads; never auto-create ──
  useEffect(() => {
    if (activeSessionId || !sessionsData) return;
    if (sessions.length > 0) {
      const id = sessions[0].id;
      const timer = setTimeout(() => {
        // Guard: user may have started a new session during the delay
        if (!useChatStore.getState().activeSessionId) setActiveSession(id);
      }, 600);
      return () => clearTimeout(timer);
    }
  }, [sessionsData]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Load messages when session changes ────────────────────────────────────
  useEffect(() => {
    if (!activeSessionId) return;
    if (skipNextLoadRef.current) {
      skipNextLoadRef.current = false;
      return;
    }
    aiApi.getMessages(activeSessionId, { limit: 100 }).then((res) => {
      setMessages(res.items);
    });
  }, [activeSessionId, setMessages]);

  // ── Auto-scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    msgsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, streamingContent]);

  // ── Close history dropdown on outside click ───────────────────────────────
  const closeHistory = useCallback(() => { setHistoryOpen(false); setMenuOpenId(null); setMenuPos(null); }, []);
  useEffect(() => {
    if (!historyOpen) return;
    function onMouseDown(e: MouseEvent) {
      if (historyRef.current && !historyRef.current.contains(e.target as Node)) {
        closeHistory();
      }
    }
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, [historyOpen]);

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
    if (isGenerating) return;

    // Lazily create a session on the very first message
    let sessionId = activeSessionId;
    let isNewSession = false;
    if (!sessionId) {
      try {
        const session = await aiApi.createSession({ dismiss_session_id: null });
        isNewSession = true;
        skipNextLoadRef.current = true;
        setActiveSession(session.id);
        void refetchSessions();
        sessionId = session.id;
      } catch {
        return;
      }
    }

    const sid = sessionId!;
    const controller = new AbortController();
    setGenerating(true, controller);

    // Optimistic user message
    const optimistic: AIMessageResponse = {
      id: `opt-${Date.now()}`,
      session_id: sid,
      role: 'user',
      content,
      actions: null,
      attached_note_ids: attachedNoteIds.length ? attachedNoteIds : null,
      created_at: new Date().toISOString(),
    };
    addMessage(optimistic);

    const payload = { content, ...(attachedNoteIds.length ? { attached_note_ids: attachedNoteIds } : {}) };

    async function runStream() {
      const gen = sendMessage(sid, payload, controller.signal);
      for await (const frame of gen) {
        switch (frame.event) {
          case 'ai:text_delta':
            appendDelta((frame.data as { delta: string }).delta);
            await new Promise<void>((resolve) => setTimeout(resolve, 0));
            break;
          case 'ai:proposal':
            pushStreamingAction(frame.data as Action);
            break;
          case 'ai:pending_confirmation':
            pushStreamingAction(frame.data as Action);
            break;
          case 'ai:done': {
            try {
              const res = await aiApi.getMessages(sid, { limit: 100 });
              if (res.items.length > 0) {
                setMessages(res.items);
              } else {
                // Server race: DB not yet committed — preserve streamed content as a local message
                const { streamingContent, streamingActions } = useChatStore.getState();
                if (streamingContent || streamingActions.length > 0) {
                  addMessage({
                    id: `ai-${Date.now()}`,
                    session_id: sid,
                    role: 'assistant',
                    content: streamingContent,
                    actions: streamingActions.length > 0 ? streamingActions : null,
                    attached_note_ids: null,
                    created_at: new Date().toISOString(),
                  });
                }
              }
            } catch {
              // keep existing messages on network failure
            }
            clearStreaming();
            setGenerating(false);
            void refetchSessions();
            break;
          }
          case 'ai:error':
            console.error('AI error', frame.data);
            clearStreaming();
            setGenerating(false);
            break;
        }
      }
    }

    try {
      await runStream();
    } catch (err: unknown) {
      const isAbort = err instanceof Error && err.name === 'AbortError';
      if (isAbort) { clearStreaming(); return; }

      // New sessions sometimes need a moment to initialize on the server — retry once
      if (isNewSession && !controller.signal.aborted) {
        try {
          await new Promise<void>((r) => setTimeout(r, 1000));
          if (!controller.signal.aborted) {
            clearStreaming();
            await runStream();
            return;
          }
        } catch (retryErr: unknown) {
          const isRetryAbort = retryErr instanceof Error && retryErr.name === 'AbortError';
          if (!isRetryAbort) {
            console.error('SSE error (retry)', retryErr);
            addMessage({
              id: `err-${Date.now()}`,
              session_id: sid,
              role: 'assistant',
              content: s.chat.generationError,
              actions: null,
              attached_note_ids: null,
              created_at: new Date().toISOString(),
            });
          }
          clearStreaming();
          return;
        }
      }

      console.error('SSE error', err);
      addMessage({
        id: `err-${Date.now()}`,
        session_id: sid,
        role: 'assistant',
        content: s.chat.generationError,
        actions: null,
        attached_note_ids: null,
        created_at: new Date().toISOString(),
      });
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
      queryClient.setQueryData(['ai-sessions'], (old: typeof sessionsData) => {
        if (!old) return old;
        return { ...old, items: old.items.filter((s) => s.id !== id) };
      });
      if (useChatStore.getState().activeSessionId === id) {
        useChatStore.getState().cancel();
        const next = sessions.find((sess) => sess.id !== id);
        setActiveSession(next?.id ?? null);
      }
    },
  });

  const renameSessionMut = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      aiApi.updateSession(id, { title }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['ai-sessions'], (old: typeof sessionsData) => {
        if (!old) return old;
        return { ...old, items: old.items.map((s) => (s.id === updated.id ? updated : s)) };
      });
      setRenamingId(null);
    },
  });

  function commitRename(id: string) {
    if (renameValue.trim()) renameSessionMut.mutate({ id, title: renameValue.trim() });
    else setRenamingId(null);
  }


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
      {/* Header + history panel wrapper */}
      <div ref={historyRef} className="flex-shrink-0 relative">
        {/* Header */}
        <div
          className="flex items-center justify-between border-b border-border"
          style={{ height: 'var(--tabbar-h)', background: 'var(--color-bg-tab)', padding: '0 20px' }}
        >
          <span className="text-[12px] font-medium text-fg-muted">
            {s.chat.assistant}
          </span>

          <div className="flex items-center gap-1.5">
            {activeSessionId && (
              <button
                className="text-[12px] font-medium text-fg rounded-md border border-border hover:bg-bg-hover disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ padding: '3px 10px' }}
                disabled={isGenerating}
                onClick={() => { setActiveSession(null); setMessages([]); closeHistory(); }}
              >
                + {s.chat.newChat}
              </button>
            )}
            <button
              className="flex items-center gap-1 text-[12px] font-medium text-fg hover:text-fg rounded-md border border-border hover:bg-bg-hover"
              style={{ padding: '3px 10px' }}
              onClick={() => setHistoryOpen((v) => !v)}
            >
              {s.chat.chatHistory}
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Session history panel — absolutely positioned so it overlays messages without shifting layout */}
        {historyOpen && (
          <div
            className="absolute left-0 right-0 border-b border-border z-30 overflow-y-auto"
            style={{ top: '100%', background: 'var(--color-bg-tab)', maxHeight: '320px' }}
            onClick={() => { setMenuOpenId(null); setMenuPos(null); }}
          >
            {sessions.length === 0 && (
              <div className="text-[12px] text-fg-muted text-center" style={{ padding: '16px' }}>
                {s.chat.noSessions}
              </div>
            )}
            {sessions.map((sess) => (
              <div
                key={sess.id}
                className={`flex items-center gap-2 cursor-pointer border-b border-border last:border-b-0 hover:bg-bg-hover
                  ${sess.id === activeSessionId ? 'bg-bg-selected/30' : ''}`}
                style={{ padding: '9px 12px' }}
              >
                {renamingId === sess.id ? (
                  <div className="flex-1" onClick={(e) => e.stopPropagation()}>
                    <input
                      autoFocus
                      className="w-full bg-bg-input border border-border-focus rounded text-[12px] text-fg outline-none"
                      style={{ padding: '4px 8px' }}
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onBlur={() => commitRename(sess.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') commitRename(sess.id);
                        if (e.key === 'Escape') setRenamingId(null);
                      }}
                    />
                    <div className="text-[10px] text-fg-muted" style={{ marginTop: '3px' }}>
                      {s.chat.renameHint}
                    </div>
                  </div>
                ) : (
                  <span
                    className="flex-1 text-[12px] truncate"
                    onClick={() => { setActiveSession(sess.id); closeHistory(); }}
                  >
                    {sess.title ?? s.chat.chat}
                  </span>
                )}

                {renamingId !== sess.id && (
                  <>
                    <span className="text-[11px] text-fg-muted flex-shrink-0">
                      {sess.last_message_at
                        ? new Date(sess.last_message_at).toLocaleDateString([], { day: 'numeric', month: 'short' })
                        : ''}
                    </span>

                    <div className="relative flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                      <button
                        className="w-6 h-6 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-bg-hover text-[16px] leading-none"
                        onClick={(e) => {
                          if (menuOpenId === sess.id) {
                            setMenuOpenId(null);
                            setMenuPos(null);
                          } else {
                            const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
                            setMenuPos({ top: rect.bottom + 2, right: window.innerWidth - rect.right });
                            setMenuOpenId(sess.id);
                          }
                        }}
                      >
                        ⋯
                      </button>
                      {menuOpenId === sess.id && menuPos && (
                        <div
                          className="fixed bg-bg-card border border-border rounded shadow-lg z-50"
                          style={{ top: menuPos.top, right: menuPos.right, minWidth: '140px', padding: '4px 0' }}
                        >
                          <button
                            className="w-full text-left text-[12px] text-fg hover:bg-bg-hover"
                            style={{ padding: '6px 12px' }}
                            onClick={() => { setRenamingId(sess.id); setRenameValue(sess.title ?? ''); setMenuOpenId(null); }}
                          >
                            {s.chat.renameSession}
                          </button>
                          <button
                            className="w-full text-left text-[12px] text-danger hover:bg-danger/10"
                            style={{ padding: '6px 12px' }}
                            onClick={() => {
                              setMenuOpenId(null);
                              if (confirm(s.chat.deleteSessionConfirm.replace('{title}', sess.title ?? s.chat.chat))) {
                                closeHistory();
                                deleteSessionMut.mutate(sess.id);
                              }
                            }}
                          >
                            {s.chat.deleteSession}
                          </button>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Messages / empty state */}
      <div className="flex-1 overflow-y-auto flex flex-col min-h-0" style={{ padding: '20px 16px', gap: '20px' }}>
        {activeSessionId === null ? (
          <ChatEmptyState
            sessions={sessions}
            onSelectSession={(id) => setActiveSession(id)}
          />
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                sessionId={activeSessionId}
              />
            ))}

            {streamingMsg && (
              <MessageBubble
                message={streamingMsg}
                sessionId={activeSessionId}
                isStreaming
                streamingContent={streamingContent}
              />
            )}


            <div ref={msgsEndRef} />
          </>
        )}
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

// ── Empty state ────────────────────────────────────────────────────────────────

function ChatEmptyState({
  sessions,
  onSelectSession,
}: {
  sessions: SessionResponse[];
  onSelectSession: (id: string) => void;
}) {
  const s = t();
  const recent = sessions.slice(0, 3);

  return (
    <div className="flex-1 flex flex-col items-center justify-center" style={{ gap: '28px' }}>

      {/* Heading */}
      <div className="flex flex-col items-center text-center" style={{ gap: '6px' }}>
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
          className="text-fg-disabled" style={{ marginBottom: '4px' }}>
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span className="text-[14px] font-medium text-fg">{s.chat.emptyHeading}</span>
        <span className="text-[12px] text-fg-muted">{s.chat.emptySubtitle}</span>
      </div>

      {/* Recent sessions */}
      {recent.length > 0 && (
        <div style={{ width: '100%', maxWidth: '260px' }}>
          <div className="text-[10px] text-fg-disabled uppercase tracking-widest" style={{ marginBottom: '8px' }}>
            {s.chat.recentChats}
          </div>
          {recent.map((sess) => (
            <button
              key={sess.id}
              onClick={() => onSelectSession(sess.id)}
              className="w-full flex items-center rounded-md hover:bg-bg-hover transition-colors text-left"
              style={{ padding: '7px 8px', gap: '8px', marginBottom: '2px' }}
            >
              <span className="flex-1 text-[12px] text-fg truncate">
                {sess.title ?? s.chat.chat}
              </span>
              <span className="text-[11px] text-fg-disabled flex-shrink-0">
                {sess.last_message_at
                  ? new Date(sess.last_message_at).toLocaleDateString([], { day: 'numeric', month: 'short' })
                  : ''}
              </span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                className="text-fg-disabled flex-shrink-0">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
