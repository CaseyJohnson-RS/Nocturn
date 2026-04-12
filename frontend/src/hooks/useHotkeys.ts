import { useEffect } from "react";
import { useNotes } from "@/stores/notes";
import { useChat } from "@/stores/chat";
import { useTabs } from "@/stores/tabs";

/**
 * Global keyboard shortcuts.
 *
 * Ctrl+N        — New note
 * Ctrl+S        — Force-save current note (flush debounce)
 * Ctrl+W        — Close active tab
 * Ctrl+Shift+P  — Toggle chat panel
 * Ctrl+Delete    — Soft-delete current note
 */
export function useHotkeys() {
  const { createNote, flushSave, deleteNote } = useNotes();
  const { toggleChat } = useChat();
  const { tabs, activeTabId, openNote, closeTab } = useTabs();

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const ctrl = e.ctrlKey || e.metaKey;

      // Ctrl+N — New note
      if (ctrl && e.key === "n") {
        e.preventDefault();
        createNote()
          .then((note) => {
            openNote(note.id, note.title || undefined);
          })
          .catch(() => {});
        return;
      }

      // Ctrl+S — Force save current note
      if (ctrl && e.key === "s") {
        e.preventDefault();
        const active = tabs.find((t) => t.id === activeTabId);
        if (active?.type === "note") {
          flushSave(active.noteId);
        }
        return;
      }

      // Ctrl+W — Close active tab
      if (ctrl && e.key === "w") {
        e.preventDefault();
        if (activeTabId) {
          closeTab(activeTabId);
        }
        return;
      }

      // Ctrl+Shift+P — Toggle chat
      if (ctrl && e.shiftKey && e.key === "P") {
        e.preventDefault();
        toggleChat();
        return;
      }

      // Ctrl+Delete — Soft-delete current note
      if (ctrl && e.key === "Delete") {
        e.preventDefault();
        const active = tabs.find((t) => t.id === activeTabId);
        if (active?.type === "note") {
          deleteNote(active.noteId);
          closeTab(active.id);
        }
        return;
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    tabs,
    activeTabId,
    createNote,
    openNote,
    flushSave,
    closeTab,
    toggleChat,
    deleteNote,
  ]);
}
