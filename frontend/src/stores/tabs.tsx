import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface NoteTab {
  id: string;
  type: "note";
  noteId: string;
  title: string;
  dirty?: boolean;
}

export interface ListTab {
  id: string;
  type: "list";
  filter: "all" | "trash" | { tagId: string; tagName: string };
  title: string;
}

export interface SearchTab {
  id: string;
  type: "search";
  title: string;
}

export type Tab = NoteTab | ListTab | SearchTab;

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------

const STORAGE_KEY = "nocturn.tabs";

interface PersistedTabs {
  tabs: Tab[];
  activeTabId: string | null;
}

function loadTabs(): PersistedTabs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as PersistedTabs;
      if (Array.isArray(parsed.tabs)) return parsed;
    }
  } catch { /* ignore */ }
  return { tabs: [], activeTabId: null };
}

function saveTabs(tabs: Tab[], activeTabId: string | null) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ tabs, activeTabId }));
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface TabsState {
  tabs: Tab[];
  activeTabId: string | null;

  openNote: (noteId: string, title?: string) => void;
  openList: (filter: ListTab["filter"], title: string) => void;
  openSearch: () => void;
  closeTab: (tabId: string) => void;
  setActiveTab: (tabId: string) => void;
  updateTabTitle: (tabId: string, title: string) => void;
  setTabDirty: (tabId: string, dirty: boolean) => void;
  reorderTabs: (fromIndex: number, toIndex: number) => void;
  closeNoteTab: (noteId: string) => void;
}

const TabsContext = createContext<TabsState | null>(null);

export function TabsProvider({ children }: { children: ReactNode }) {
  const [{ tabs, activeTabId }, setState] = useState<PersistedTabs>(loadTabs);

  // Helper: update state and persist
  const update = useCallback(
    (fn: (prev: PersistedTabs) => PersistedTabs) => {
      setState((prev) => {
        const next = fn(prev);
        saveTabs(next.tabs, next.activeTabId);
        return next;
      });
    },
    [],
  );

  const openNote = useCallback(
    (noteId: string, title?: string) => {
      update((prev) => {
        const existing = prev.tabs.find(
          (t) => t.type === "note" && t.noteId === noteId,
        );
        if (existing) {
          return { ...prev, activeTabId: existing.id };
        }
        const tab: NoteTab = {
          id: `note-${noteId}`,
          type: "note",
          noteId,
          title: title || "Untitled",
        };
        return {
          tabs: [...prev.tabs, tab],
          activeTabId: tab.id,
        };
      });
    },
    [update],
  );

  const openList = useCallback(
    (filter: ListTab["filter"], title: string) => {
      update((prev) => {
        // Find existing list tab with same filter
        const existing = prev.tabs.find((t) => {
          if (t.type !== "list") return false;
          if (typeof filter === "string" && typeof t.filter === "string")
            return t.filter === filter;
          if (typeof filter === "object" && typeof t.filter === "object")
            return t.filter.tagId === filter.tagId;
          return false;
        });
        if (existing) {
          return { ...prev, activeTabId: existing.id };
        }
        const id =
          typeof filter === "string"
            ? `list-${filter}`
            : `list-tag-${filter.tagId}`;
        const tab: ListTab = { id, type: "list", filter, title };
        return {
          tabs: [...prev.tabs, tab],
          activeTabId: tab.id,
        };
      });
    },
    [update],
  );

  const openSearch = useCallback(() => {
    update((prev) => {
      const existing = prev.tabs.find((t) => t.type === "search");
      if (existing) {
        return { ...prev, activeTabId: existing.id };
      }
      const tab: SearchTab = { id: "search", type: "search", title: "Search" };
      return {
        tabs: [...prev.tabs, tab],
        activeTabId: tab.id,
      };
    });
  }, [update]);

  const closeTab = useCallback(
    (tabId: string) => {
      update((prev) => {
        const idx = prev.tabs.findIndex((t) => t.id === tabId);
        if (idx === -1) return prev;
        const next = prev.tabs.filter((t) => t.id !== tabId);
        let nextActive = prev.activeTabId;
        if (prev.activeTabId === tabId) {
          // Activate neighbor tab
          const neighbor = next[Math.min(idx, next.length - 1)];
          nextActive = neighbor?.id ?? null;
        }
        return { tabs: next, activeTabId: nextActive };
      });
    },
    [update],
  );

  const closeNoteTab = useCallback(
    (noteId: string) => {
      update((prev) => {
        const tab = prev.tabs.find(
          (t) => t.type === "note" && t.noteId === noteId,
        );
        if (!tab) return prev;
        const idx = prev.tabs.indexOf(tab);
        const next = prev.tabs.filter((t) => t.id !== tab.id);
        let nextActive = prev.activeTabId;
        if (prev.activeTabId === tab.id) {
          const neighbor = next[Math.min(idx, next.length - 1)];
          nextActive = neighbor?.id ?? null;
        }
        return { tabs: next, activeTabId: nextActive };
      });
    },
    [update],
  );

  const setActiveTab = useCallback(
    (tabId: string) => {
      update((prev) => ({ ...prev, activeTabId: tabId }));
    },
    [update],
  );

  const updateTabTitle = useCallback(
    (tabId: string, title: string) => {
      update((prev) => ({
        ...prev,
        tabs: prev.tabs.map((t) => (t.id === tabId ? { ...t, title } : t)),
      }));
    },
    [update],
  );

  const setTabDirty = useCallback(
    (tabId: string, dirty: boolean) => {
      update((prev) => ({
        ...prev,
        tabs: prev.tabs.map((t) =>
          t.id === tabId && t.type === "note" ? { ...t, dirty } : t,
        ),
      }));
    },
    [update],
  );

  const reorderTabs = useCallback(
    (fromIndex: number, toIndex: number) => {
      update((prev) => {
        const next = [...prev.tabs];
        const [moved] = next.splice(fromIndex, 1);
        next.splice(toIndex, 0, moved);
        return { ...prev, tabs: next };
      });
    },
    [update],
  );

  return (
    <TabsContext.Provider
      value={{
        tabs,
        activeTabId,
        openNote,
        openList,
        openSearch,
        closeTab,
        setActiveTab,
        updateTabTitle,
        setTabDirty,
        reorderTabs,
        closeNoteTab,
      }}
    >
      {children}
    </TabsContext.Provider>
  );
}

export function useTabs() {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error("useTabs must be inside TabsProvider");
  return ctx;
}
