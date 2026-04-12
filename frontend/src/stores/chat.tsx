import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import type {
  ChatSession,
  ChatMessage,
} from "@/api/types";
import * as aiApi from "@/api/ai";

interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  messages: ChatMessage[];
  streamingText: string;
  isStreaming: boolean;
  chatOpen: boolean;
  attachedNoteIds: string[];

  setChatOpen: (open: boolean) => void;
  attachNote: (noteId: string) => void;
  detachNote: (noteId: string) => void;
  toggleChat: () => void;
  fetchSessions: () => Promise<void>;
  selectSession: (id: string | null) => Promise<void>;
  createSession: () => Promise<ChatSession>;
  deleteSession: (id: string) => Promise<void>;
  sendMessage: (text: string, noteIds?: string[]) => Promise<void>;
  cancelGeneration: () => void;
  applyAction: (messageId: string, actionId: string) => Promise<void>;
  dismissAction: (messageId: string, actionId: string) => Promise<void>;
  confirmBulk: (confirmationId: string) => Promise<void>;
  dismissBulk: (confirmationId: string) => Promise<void>;
}

const ChatContext = createContext<ChatState | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [attachedNoteIds, setAttachedNoteIds] = useState<string[]>([]);

  const abortRef = useRef<AbortController | null>(null);

  const attachNote = useCallback((noteId: string) => {
    setAttachedNoteIds((prev) =>
      prev.includes(noteId) ? prev : [...prev, noteId],
    );
    setChatOpen(true);
  }, []);

  const detachNote = useCallback((noteId: string) => {
    setAttachedNoteIds((prev) => prev.filter((id) => id !== noteId));
  }, []);

  const toggleChat = useCallback(() => {
    setChatOpen((prev) => !prev);
  }, []);

  const fetchSessions = useCallback(async () => {
    const resp = await aiApi.listSessions();
    setSessions(resp.items);
  }, []);

  const selectSession = useCallback(async (id: string | null) => {
    setCurrentSessionId(id);
    if (!id) {
      setMessages([]);
      return;
    }
    const resp = await aiApi.getSessionMessages(id);
    setMessages(resp.items);
  }, []);

  const createSession = useCallback(async () => {
    const session = await aiApi.createSession();
    setSessions((prev) => [session, ...prev]);
    setCurrentSessionId(session.id);
    setMessages([]);
    return session;
  }, []);

  const deleteSession = useCallback(
    async (id: string) => {
      await aiApi.deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (currentSessionId === id) {
        setCurrentSessionId(null);
        setMessages([]);
      }
    },
    [currentSessionId],
  );

  const sendMessage = useCallback(
    async (text: string, noteIds?: string[]) => {
      // Merge explicit noteIds with store attachments
      const allNoteIds = Array.from(
        new Set([...(noteIds ?? []), ...attachedNoteIds]),
      );
      setAttachedNoteIds([]);
      let sessionId = currentSessionId;

      // Auto-create session if none
      if (!sessionId) {
        const session = await aiApi.createSession();
        setSessions((prev) => [session, ...prev]);
        setCurrentSessionId(session.id);
        sessionId = session.id;
      }

      // Optimistic user message
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        session_id: sessionId,
        role: "user",
        content: text,
        actions: null,
        attached_note_ids: allNoteIds.length ? allNoteIds : null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setStreamingText("");
      setIsStreaming(true);

      const abort = new AbortController();
      abortRef.current = abort;

      try {
        await aiApi.sendMessage(
          sessionId,
          text,
          allNoteIds,
          (event, data) => {
            if (event === "ai:text_delta" || (!event && data.delta)) {
              setStreamingText((prev) => prev + (data.delta as string));
            } else if (event === "ai:proposal" || event === "ai:pending_confirmation") {
              // Action arrived during stream — will be included in done message
            } else if (event === "ai:done") {
              const msg = data.message as ChatMessage | undefined;
              if (msg) {
                setMessages((prev) => {
                  // Replace optimistic user msg and add assistant
                  const filtered = prev.filter((m) => m.id !== userMsg.id);
                  // Find if user message is in the done payload
                  return [...filtered, msg];
                });
              }
              setStreamingText("");
            } else if (event === "ai:error") {
              setStreamingText("");
            }
          },
          abort.signal,
        );
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          console.error("sendMessage error:", err);
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
        // Refresh session messages to get clean state
        if (sessionId) {
          try {
            const resp = await aiApi.getSessionMessages(sessionId);
            setMessages(resp.items);
            // Refresh session list to pick up updated titles
            const sessResp = await aiApi.listSessions();
            setSessions(sessResp.items);
          } catch {
            /* ignore */
          }
        }
      }
    },
    [currentSessionId, attachedNoteIds],
  );

  const cancelGeneration = useCallback(() => {
    abortRef.current?.abort();
    if (currentSessionId) {
      aiApi.cancelGeneration(currentSessionId).catch(() => {});
    }
  }, [currentSessionId]);

  const applyAction = useCallback(
    async (messageId: string, actionId: string) => {
      if (!currentSessionId) return;
      const updated = await aiApi.updateActionStatus(
        currentSessionId,
        messageId,
        actionId,
        "applied",
      );
      setMessages((prev) =>
        prev.map((m) => (m.id === updated.id ? updated : m)),
      );
    },
    [currentSessionId],
  );

  const dismissAction = useCallback(
    async (messageId: string, actionId: string) => {
      if (!currentSessionId) return;
      const updated = await aiApi.updateActionStatus(
        currentSessionId,
        messageId,
        actionId,
        "dismissed",
      );
      setMessages((prev) =>
        prev.map((m) => (m.id === updated.id ? updated : m)),
      );
    },
    [currentSessionId],
  );

  const confirmBulk = useCallback(
    async (confirmationId: string) => {
      if (!currentSessionId) return;
      setIsStreaming(true);
      try {
        await aiApi.confirmBulk(currentSessionId, confirmationId, (event, data) => {
          if (event === "ai:done") {
            const msg = data.message as ChatMessage | undefined;
            if (msg) {
              setMessages((prev) =>
                prev.map((m) => (m.id === msg.id ? msg : m)),
              );
            }
          }
        });
        // Refresh
        const resp = await aiApi.getSessionMessages(currentSessionId);
        setMessages(resp.items);
      } finally {
        setIsStreaming(false);
      }
    },
    [currentSessionId],
  );

  const dismissBulk = useCallback(
    async (confirmationId: string) => {
      if (!currentSessionId) return;
      const updated = await aiApi.dismissBulk(currentSessionId, confirmationId);
      setMessages((prev) =>
        prev.map((m) => (m.id === updated.id ? updated : m)),
      );
    },
    [currentSessionId],
  );

  return (
    <ChatContext.Provider
      value={{
        sessions,
        currentSessionId,
        messages,
        streamingText,
        isStreaming,
        chatOpen,
        attachedNoteIds,
        setChatOpen,
        attachNote,
        detachNote,
        toggleChat,
        fetchSessions,
        selectSession,
        createSession,
        deleteSession,
        sendMessage,
        cancelGeneration,
        applyAction,
        dismissAction,
        confirmBulk,
        dismissBulk,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be inside ChatProvider");
  return ctx;
}
