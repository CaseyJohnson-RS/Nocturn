import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type SidebarPanel = 'notes' | 'search' | 'tags' | 'trash' | 'admin';

export interface NoteTabId {
  type: 'note';
  id: string;
}

export interface DiffTabId {
  type: 'diff';
  id: string;
}

export interface PanelTabId {
  type: 'panel';
  panel: SidebarPanel;
}

export type TabId = NoteTabId | DiffTabId | PanelTabId;

export function tabKey(tab: TabId): string {
  if (tab.type === 'panel') return `panel:${tab.panel}`;
  return `${tab.type}:${tab.id}`;
}

export type NoteTabStatus = 'dirty' | 'saving' | 'conflict' | null;

interface UIState {
  ephemeralNoteIds: Set<string>;
  markEphemeral: (id: string) => void;
  clearEphemeral: (id: string) => void;
  openTabs: TabId[];
  activeTabKey: string | null;
  chatOpen: boolean;
  profileOpen: boolean;
  offlineBanner: boolean;
  readonlyBanner: boolean;
  attachedNoteIds: string[];
  noteTabStatus: Record<string, NoteTabStatus>;
  searchQuery: string;
  searchSubmitted: string;

  openTab: (tab: TabId) => void;
  closeTab: (tab: TabId) => void;
  setActiveTab: (tab: TabId) => void;
  toggleChat: () => void;
  setProfileOpen: (v: boolean) => void;
  setOfflineBanner: (v: boolean) => void;
  setReadonlyBanner: (v: boolean) => void;
  attachNote: (id: string) => void;
  detachNote: (id: string) => void;
  clearAttachedNotes: () => void;
  setNoteTabStatus: (noteId: string, status: NoteTabStatus) => void;
  setSearchQuery: (q: string) => void;
  setSearchSubmitted: (q: string) => void;
}

const INITIAL_TAB: PanelTabId = { type: 'panel', panel: 'notes' };

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      openTabs: [INITIAL_TAB],
      activeTabKey: tabKey(INITIAL_TAB),
      chatOpen: true,
      profileOpen: false,
      offlineBanner: false,
      readonlyBanner: false,
      attachedNoteIds: [],
      noteTabStatus: {},
      ephemeralNoteIds: new Set(),
      searchQuery: '',
      searchSubmitted: '',

      openTab: (tab) => {
        const key = tabKey(tab);
        const { openTabs } = get();
        const exists = openTabs.some((t) => tabKey(t) === key);
        set({
          openTabs: exists ? openTabs : [...openTabs, tab],
          activeTabKey: key,
        });
      },

      closeTab: (tab) => {
        const key = tabKey(tab);
        const { openTabs, activeTabKey } = get();
        const next = openTabs.filter((t) => tabKey(t) !== key);
        let nextActive = activeTabKey;
        if (activeTabKey === key) {
          const idx = openTabs.findIndex((t) => tabKey(t) === key);
          const fallback = next[idx] ?? next[idx - 1] ?? null;
          nextActive = fallback ? tabKey(fallback) : null;
        }
        set({ openTabs: next, activeTabKey: nextActive });
      },

      setActiveTab: (tab) => set({ activeTabKey: tabKey(tab) }),

      toggleChat: () => set((s) => ({ chatOpen: !s.chatOpen })),
      setProfileOpen: (v) => set({ profileOpen: v }),
      setOfflineBanner: (v) => set({ offlineBanner: v }),
      setReadonlyBanner: (v) => set({ readonlyBanner: v }),
      attachNote: (id) =>
        set((s) =>
          s.attachedNoteIds.length < 5 && !s.attachedNoteIds.includes(id)
            ? { attachedNoteIds: [...s.attachedNoteIds, id] }
            : s,
        ),
      detachNote: (id) =>
        set((s) => ({ attachedNoteIds: s.attachedNoteIds.filter((i) => i !== id) })),
      clearAttachedNotes: () => set({ attachedNoteIds: [] }),
      setNoteTabStatus: (noteId, status) =>
        set((s) => ({ noteTabStatus: { ...s.noteTabStatus, [noteId]: status } })),
      markEphemeral: (id) =>
        set((s) => ({ ephemeralNoteIds: new Set([...s.ephemeralNoteIds, id]) })),
      clearEphemeral: (id) =>
        set((s) => {
          const next = new Set(s.ephemeralNoteIds);
          next.delete(id);
          return { ephemeralNoteIds: next };
        }),
      setSearchQuery: (q) => set({ searchQuery: q }),
      setSearchSubmitted: (q) => set({ searchSubmitted: q }),
    }),
    {
      name: 'nocturn-ui',
      partialize: (state) => ({
        openTabs: state.openTabs,
        activeTabKey: state.activeTabKey,
        searchQuery: state.searchQuery,
        searchSubmitted: state.searchSubmitted,
        chatOpen: state.chatOpen,
      }),
    },
  ),
);
