import { useCallback, useEffect, useState } from "react";
import { NotesProvider, useNotes } from "@/stores/notes";
import { ChatProvider, useChat } from "@/stores/chat";
import { TabsProvider } from "@/stores/tabs";
import { Navbar } from "@/components/layout/Navbar";
import { EditorPanel } from "@/components/editor/EditorPanel";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { ResizeHandle } from "@/components/layout/ResizeHandle";
import { Toaster } from "@/components/ui/toaster";
import { useHotkeys } from "@/hooks/useHotkeys";

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------

const CHAT_WIDTH_KEY = "nocturn.chatWidth";
const DEFAULT_CHAT_WIDTH = 384; // 24rem
const MIN_CHAT_WIDTH = 280;
const MAX_CHAT_WIDTH = 640;

function loadChatWidth(): number {
  const stored = localStorage.getItem(CHAT_WIDTH_KEY);
  if (stored) {
    const n = parseInt(stored, 10);
    if (!isNaN(n)) return Math.max(MIN_CHAT_WIDTH, Math.min(MAX_CHAT_WIDTH, n));
  }
  return DEFAULT_CHAT_WIDTH;
}

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

function AppContent() {
  const { fetchNotes, fetchTags } = useNotes();
  const { chatOpen } = useChat();
  const [chatWidth, setChatWidth] = useState(loadChatWidth);

  // Global keyboard shortcuts
  useHotkeys();

  useEffect(() => {
    fetchNotes();
    fetchTags();
  }, [fetchNotes, fetchTags]);

  const handleChatResize = useCallback((delta: number) => {
    setChatWidth((prev) => {
      const next = Math.max(MIN_CHAT_WIDTH, Math.min(MAX_CHAT_WIDTH, prev + delta));
      localStorage.setItem(CHAT_WIDTH_KEY, String(next));
      return next;
    });
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Navbar — fixed width */}
      <Navbar />

      {/* Editor — takes remaining space */}
      <EditorPanel />

      {/* Chat — collapsible, resizable */}
      {chatOpen && (
        <>
          <ResizeHandle direction="right" onResize={handleChatResize} />
          <aside
            className="shrink-0 border-l border-border bg-card overflow-hidden"
            style={{ width: chatWidth }}
          >
            <ChatPanel />
          </aside>
        </>
      )}

      <Toaster />
    </div>
  );
}

export default function AppLayout() {
  return (
    <TabsProvider>
      <NotesProvider>
        <ChatProvider>
          <AppContent />
        </ChatProvider>
      </NotesProvider>
    </TabsProvider>
  );
}
