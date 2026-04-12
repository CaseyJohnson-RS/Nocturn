import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Note, NoteListItem, Tag } from "@/api/types";
import * as notesApi from "@/api/notes";
import * as tagsApi from "@/api/tags";

// ---------------------------------------------------------------------------
// Per-note save state (for multi-tab debounced saving)
// ---------------------------------------------------------------------------

interface PendingSave {
  noteId: string;
  body: { title?: string | null; content?: string | null; version: number };
  timer: ReturnType<typeof setTimeout>;
}

// ---------------------------------------------------------------------------
// Context interface
// ---------------------------------------------------------------------------

interface NotesState {
  /* Global lists */
  notes: NoteListItem[];
  tags: Tag[];
  loading: boolean;

  /* List operations */
  fetchNotes: (params?: {
    deleted?: boolean;
    search?: string;
    tag_ids?: string[];
  }) => Promise<NoteListItem[]>;
  fetchTags: () => Promise<void>;

  /* Note CRUD */
  createNote: () => Promise<Note>;
  getNote: (id: string) => Promise<Note>;
  saveNote: (
    noteId: string,
    body: { title?: string | null; content?: string | null },
    version: number,
    /** Called with the updated note on successful save */
    onSaved?: (note: Note) => void,
  ) => void;
  flushSave: (noteId: string) => Promise<void>;
  deleteNote: (id: string, permanent?: boolean) => Promise<void>;
  restoreNote: (id: string) => Promise<void>;

  /* Tags on notes */
  updateNoteTags: (
    noteId: string,
    tagIds: string[],
  ) => Promise<Note>;
  createTag: (name: string) => Promise<Tag>;

  /* List helpers */
  updateNoteInList: (
    noteId: string,
    data: Partial<NoteListItem>,
  ) => void;
  removeNoteFromList: (noteId: string) => void;
  isSaving: (noteId: string) => boolean;
}

const NotesContext = createContext<NotesState | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function NotesProvider({ children }: { children: ReactNode }) {
  const [notes, setNotes] = useState<NoteListItem[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(false);

  // Per-note pending saves (keyed by noteId)
  const pendingSaves = useRef<Map<string, PendingSave>>(new Map());
  const savingIds = useRef<Set<string>>(new Set());
  // Force re-render when saving state changes
  const [, forceUpdate] = useState(0);

  // ------ Cleanup on unmount ------
  useEffect(() => {
    return () => {
      for (const ps of pendingSaves.current.values()) {
        clearTimeout(ps.timer);
      }
      pendingSaves.current.clear();
    };
  }, []);

  // ------ Keepalive on page unload ------
  useEffect(() => {
    const handleBeforeUnload = () => {
      for (const ps of pendingSaves.current.values()) {
        void notesApi.updateNote(ps.noteId, ps.body, { keepalive: true });
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, []);

  // ------ List operations ------

  const fetchNotes = useCallback(
    async (params?: {
      deleted?: boolean;
      search?: string;
      tag_ids?: string[];
    }) => {
      setLoading(true);
      try {
        const resp = await notesApi.listNotes({
          limit: 200,
          deleted: params?.deleted,
          search: params?.search,
          tag_ids: params?.tag_ids,
        });
        setNotes(resp.items);
        return resp.items;
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  const fetchTags = useCallback(async () => {
    const resp = await tagsApi.listTags();
    setTags(resp.items);
  }, []);

  // ------ Note CRUD ------

  const createNote = useCallback(async () => {
    const note = await notesApi.createNote({ title: null, content: "" });
    setNotes((prev) => [
      {
        id: note.id,
        title: note.title,
        updated_at: note.updated_at,
        deleted_at: null,
      },
      ...prev,
    ]);
    return note;
  }, []);

  const getNote = useCallback(async (id: string) => {
    return notesApi.getNote(id);
  }, []);

  const flushSave = useCallback(async (noteId: string) => {
    const ps = pendingSaves.current.get(noteId);
    if (!ps) return;
    clearTimeout(ps.timer);
    pendingSaves.current.delete(noteId);
    savingIds.current.add(noteId);
    forceUpdate((n) => n + 1);
    try {
      await notesApi.updateNote(ps.noteId, ps.body);
    } finally {
      savingIds.current.delete(noteId);
      forceUpdate((n) => n + 1);
    }
  }, []);

  const saveNote = useCallback(
    (
      noteId: string,
      body: { title?: string | null; content?: string | null },
      version: number,
      onSaved?: (note: Note) => void,
    ) => {
      // Cancel previous timer for this note
      const existing = pendingSaves.current.get(noteId);
      if (existing) clearTimeout(existing.timer);

      const saveBody = { ...body, version };

      // Optimistic list update
      setNotes((prev) =>
        prev.map((n) =>
          n.id === noteId
            ? {
                ...n,
                title: body.title !== undefined ? body.title : n.title,
                updated_at: new Date().toISOString(),
              }
            : n,
        ),
      );

      const timer = setTimeout(async () => {
        pendingSaves.current.delete(noteId);
        savingIds.current.add(noteId);
        forceUpdate((n) => n + 1);
        try {
          const updated = await notesApi.updateNote(noteId, saveBody);
          onSaved?.(updated);
        } finally {
          savingIds.current.delete(noteId);
          forceUpdate((n) => n + 1);
        }
      }, 600);

      pendingSaves.current.set(noteId, { noteId, body: saveBody, timer });
    },
    [],
  );

  const deleteNote = useCallback(
    async (id: string, permanent = false) => {
      // Flush any pending save first
      await flushSave(id);
      if (permanent) {
        await notesApi.deleteNote(id);
      } else {
        await notesApi.deleteNote(id);
      }
      setNotes((prev) => prev.filter((n) => n.id !== id));
    },
    [flushSave],
  );

  const restoreNote = useCallback(async (id: string) => {
    const restored = await notesApi.restoreNote(id);
    setNotes((prev) =>
      prev.map((n) =>
        n.id === id
          ? { ...n, deleted_at: null, updated_at: restored.updated_at }
          : n,
      ),
    );
  }, []);

  // ------ Tags ------

  const updateNoteTags = useCallback(
    async (noteId: string, tagIds: string[]) => {
      return notesApi.updateNoteTags(noteId, tagIds);
    },
    [],
  );

  const createTag = useCallback(async (name: string) => {
    const tag = await tagsApi.createTag(name);
    setTags((prev) => [...prev, tag]);
    return tag;
  }, []);

  // ------ List helpers ------

  const updateNoteInList = useCallback(
    (noteId: string, data: Partial<NoteListItem>) => {
      setNotes((prev) =>
        prev.map((n) => (n.id === noteId ? { ...n, ...data } : n)),
      );
    },
    [],
  );

  const removeNoteFromList = useCallback((noteId: string) => {
    setNotes((prev) => prev.filter((n) => n.id !== noteId));
  }, []);

  const isSaving = useCallback(
    (noteId: string) =>
      savingIds.current.has(noteId) || pendingSaves.current.has(noteId),
    [],
  );

  return (
    <NotesContext.Provider
      value={{
        notes,
        tags,
        loading,
        fetchNotes,
        fetchTags,
        createNote,
        getNote,
        saveNote,
        flushSave,
        deleteNote,
        restoreNote,
        updateNoteTags,
        createTag,
        updateNoteInList,
        removeNoteFromList,
        isSaving,
      }}
    >
      {children}
    </NotesContext.Provider>
  );
}

export function useNotes() {
  const ctx = useContext(NotesContext);
  if (!ctx) throw new Error("useNotes must be inside NotesProvider");
  return ctx;
}
