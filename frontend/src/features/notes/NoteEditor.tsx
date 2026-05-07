import { useEffect, useRef, useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { EditorView, keymap } from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands';
import { markdown } from '@codemirror/lang-markdown';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { notesApi } from '@/api/notes';
import { tagsApi } from '@/api/tags';
import { isAxiosError } from '@/api/client';
import { useUIStore } from '@/stores/ui';
import { t } from '@/i18n';
import type { NoteResponse, TagResponse } from '@/types/api';

const AUTOSAVE_DELAY = 1500;

interface NoteEditorProps {
  noteId: string;
}

export default function NoteEditor({ noteId }: NoteEditorProps) {
  const s = t();
  const qc = useQueryClient();
  const { attachedNoteIds, attachNote, detachNote } = useUIStore();

  // ── Load note (before useState so lazy initializers can read from cache) ──
  const { data: note } = useQuery<NoteResponse>({
    queryKey: ['note', noteId],
    queryFn: () => notesApi.get(noteId),
  });

  // Lazy initializers: when the tab is re-opened, React Query already has the
  // note in cache and returns it synchronously, so title/content are correct
  // on the very first render — no flash of empty header.
  const [title, setTitle] = useState(() => note?.title ?? '');
  const [content, setContent] = useState(() => note?.content ?? '');
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [tagSearch, setTagSearch] = useState('');
  const [tagFocused, setTagFocused] = useState(false);

  // syncedNoteIdRef: tracks which note ID we last synced local state from.
  // Lets the effect below skip resets triggered by autosaves (same note, new
  // version) while still resetting when the user switches to a different note.
  const syncedNoteIdRef = useRef<string | null>(null);
  const versionRef = useRef<number>(note?.version ?? 1);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editorDivRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  // Refs keep the CodeMirror closure (created once on mount) always fresh
  const titleRef = useRef(title);
  titleRef.current = title;
  const contentRef = useRef(content);
  contentRef.current = content;

  // Sync note → local state only when the note ID changes (note switch or
  // first load). Skips saves (same ID, bumped version) so autosave never
  // overwrites text the user is actively typing.
  useEffect(() => {
    if (!note) return;
    versionRef.current = note.version; // always keep version fresh for conflict detection
    if (note.id === syncedNoteIdRef.current) return;
    syncedNoteIdRef.current = note.id;
    setTitle(note.title ?? '');
    setContent(note.content ?? '');
    setDirty(false);
    setConflict(false);
  }, [note]);

  // ── Tags ───────────────────────────────────────────────────────────────────
  const { data: allTags } = useQuery<{ items: TagResponse[] }>({
    queryKey: ['tags'],
    queryFn: () => tagsApi.list({ limit: 100 }),
  });

  const setTagsMut = useMutation({
    mutationFn: (ids: string[]) => notesApi.setTags(noteId, { tag_ids: ids }),
    onSuccess: (updated) => qc.setQueryData(['note', noteId], updated),
  });

  function removeTag(tagId: string) {
    if (!note) return;
    setTagsMut.mutate(note.tags.map((tg) => tg.id).filter((id) => id !== tagId));
  }

  function addTagById(tagId: string) {
    if (!note) return;
    const current = note.tags.map((tg) => tg.id);
    if (current.includes(tagId)) return;
    setTagsMut.mutate([...current, tagId]);
    setTagSearch('');
  }

  async function addOrCreateTag(name: string) {
    if (!note) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    const existing = (allTags?.items ?? []).find(
      (tg) => tg.name.toLowerCase() === trimmed.toLowerCase(),
    );
    if (existing) {
      addTagById(existing.id);
    } else {
      try {
        const newTag = await tagsApi.create({ name: trimmed });
        void qc.invalidateQueries({ queryKey: ['tags'] });
        const current = note.tags.map((tg) => tg.id);
        if (!current.includes(newTag.id)) setTagsMut.mutate([...current, newTag.id]);
        setTagSearch('');
      } catch { /* ignore */ }
    }
  }

  const tagSuggestions = (allTags?.items ?? []).filter((tag) => {
    if (!tagSearch.trim()) return false;
    const already = note?.tags.some((tg) => tg.id === tag.id);
    return !already && tag.name.toLowerCase().includes(tagSearch.toLowerCase());
  });

  const showCreateOption =
    tagSearch.trim().length > 0 &&
    !(allTags?.items ?? []).some(
      (tg) => tg.name.toLowerCase() === tagSearch.trim().toLowerCase(),
    );

  // ── Save ───────────────────────────────────────────────────────────────────
  const save = useCallback(
    async (t2: string, c: string) => {
      setSaving(true);
      try {
        const updated = await notesApi.update(noteId, {
          title: t2 || null,
          content: c || null,
          version: versionRef.current,
        });
        versionRef.current = updated.version;
        qc.setQueryData(['note', noteId], updated);
        void qc.invalidateQueries({ queryKey: ['notes'] });
        setDirty(false);
      } catch (err) {
        if (isAxiosError(err) && err.response?.status === 409) setConflict(true);
      } finally {
        setSaving(false);
      }
    },
    [noteId, qc],
  );

  function scheduleSave(t2: string, c: string) {
    setDirty(true);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => void save(t2, c), AUTOSAVE_DELAY);
  }

  // ── CodeMirror (always mounted so useEffect([]) can attach on first render) ─
  useEffect(() => {
    if (!editorDivRef.current) return;
    const view = new EditorView({
      state: EditorState.create({
        doc: '',
        extensions: [
          history(),
          markdown(),
          EditorView.lineWrapping,
          keymap.of([...defaultKeymap, ...historyKeymap]),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) {
              const newContent = update.state.doc.toString();
              setContent(newContent);
              scheduleSave(titleRef.current, newContent);
            }
          }),
          EditorView.theme({
            '&': {
              background: 'var(--color-bg-base)',
              color: 'var(--color-fg)',
              height: '100%',
            },
            '.cm-scroller': { overflow: 'auto' },
            '.cm-content': {
              caretColor: 'var(--color-fg)',
              padding: '28px 36px',
              minHeight: '100%',
            },
          }),
        ],
      }),
      parent: editorDivRef.current,
    });
    viewRef.current = view;
    return () => { view.destroy(); viewRef.current = null; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync content into CM when note switches
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const newDoc = note?.content ?? '';
    const current = view.state.doc.toString();
    if (current !== newDoc) {
      view.dispatch({ changes: { from: 0, to: current.length, insert: newDoc } });
    }
  }, [note?.id]);

  function handleTitleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter')
      editorDivRef.current?.querySelector<HTMLElement>('.cm-content')?.focus();
  }

  // ── Attach to chat ─────────────────────────────────────────────────────────
  const isAttached = attachedNoteIds.includes(noteId);
  const atLimit = attachedNoteIds.length >= 5;

  function handleAttach() {
    if (isAttached) detachNote(noteId);
    else if (!atLimit) attachNote(noteId);
  }

  // ── Save status dot ────────────────────────────────────────────────────────
  // Matches prototype: colored 6px dot + label text
  let dotClass = '';
  let dotLabel = '';
  if (note) {
    if (conflict) {
      dotClass = 'bg-danger';
      dotLabel = s.notes.versionConflict;
    } else if (saving) {
      dotClass = 'bg-warning save-dot-pulse';
      dotLabel = s.notes.saving;
    } else if (dirty) {
      dotClass = 'bg-warning';
      dotLabel = '';
    } else {
      dotClass = 'bg-success';
      dotLabel = s.notes.saved;
    }
  }

  return (
    <div className="h-full flex flex-col">

      {/* ── Toolbar: save-dot + attach button, right-aligned ── */}
      <div
        className="flex-shrink-0 flex items-center justify-end gap-4 px-6 border-b border-border"
        style={{ height: 'var(--tabbar-h)', background: 'var(--color-bg-tab)' }}
      >
        {note && (
          <div className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotClass}`} />
            {dotLabel && (
              <span className="text-[11px] text-fg-muted">{dotLabel}</span>
            )}
          </div>
        )}

        <button
          className={`text-[11px] px-2 py-0.5 rounded border transition-colors ${
            isAttached
              ? 'border-accent text-accent bg-accent/10'
              : atLimit
              ? 'border-border text-fg-disabled cursor-not-allowed opacity-50'
              : 'border-border text-fg-muted hover:text-fg hover:border-border-focus'
          }`}
          onClick={handleAttach}
          disabled={!isAttached && atLimit}
          title={!isAttached && atLimit ? s.notes.attachLimit : undefined}
        >
          📎 {isAttached ? s.notes.detachFromChat : s.notes.attachToChat}
        </button>
      </div>

      {/* ── Editor head: title + tags ── */}
      {note ? (
        <div className="flex-shrink-0 px-7 pt-5 pb-4 border-b border-border">
          {/* Title */}
          <input
            className="w-full bg-transparent border-none outline-none text-[20px] font-semibold text-fg placeholder:text-fg-disabled leading-tight"
            placeholder={s.notes.untitled}
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              scheduleSave(e.target.value, contentRef.current);
            }}
            onKeyDown={handleTitleKeyDown}
          />

          {/* Tags row */}
          <div className="flex flex-wrap items-center gap-2 mt-3">
            {note.tags.map((tag) => (
              <span
                key={tag.id}
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-bg-input border border-border rounded text-[12px] text-fg"
              >
                #{tag.name}
                <button
                  className="text-fg-muted hover:text-danger text-[13px] leading-none"
                  onClick={() => removeTag(tag.id)}
                >
                  ×
                </button>
              </span>
            ))}

            {/* Inline tag autocomplete — looks like "+ тег" plain text */}
            <div className="relative">
              <input
                className="text-[12px] text-fg-muted bg-transparent outline-none border-none placeholder:text-fg-disabled w-16 cursor-text"
                placeholder="+ тег"
                value={tagSearch}
                onChange={(e) => setTagSearch(e.target.value)}
                onFocus={() => setTagFocused(true)}
                onBlur={() => setTimeout(() => setTagFocused(false), 150)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (tagSuggestions.length > 0) addTagById(tagSuggestions[0].id);
                    else if (tagSearch.trim()) void addOrCreateTag(tagSearch);
                  } else if (e.key === 'Escape') {
                    setTagSearch('');
                    setTagFocused(false);
                  }
                }}
              />

              {tagFocused && (tagSuggestions.length > 0 || showCreateOption) && (
                <div className="absolute top-full mt-1 left-0 z-[100] bg-bg-card border border-border rounded shadow-xl min-w-[160px] max-h-40 overflow-y-auto">
                  {tagSuggestions.map((tag) => (
                    <div
                      key={tag.id}
                      className="px-2.5 py-1.5 text-[12px] text-fg hover:bg-bg-hover cursor-pointer"
                      onMouseDown={() => addTagById(tag.id)}
                    >
                      #{tag.name}
                    </div>
                  ))}
                  {showCreateOption && (
                    <div
                      className="px-2.5 py-1.5 text-[12px] text-accent hover:bg-bg-hover cursor-pointer border-t border-border first:border-t-0"
                      onMouseDown={() => void addOrCreateTag(tagSearch)}
                    >
                      + {s.notes.newTag} «{tagSearch.trim()}»
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Loading skeleton */
        <div className="flex-shrink-0 px-7 pt-5 pb-4 border-b border-border">
          <div className="h-7 w-56 bg-bg-hover rounded animate-pulse mb-3" />
          <div className="h-4 w-28 bg-bg-hover rounded animate-pulse" />
        </div>
      )}

      {/* ── Split: raw CodeMirror (left) | rendered preview (right) ──
          Both always in the DOM — editorDivRef must be present on mount
          so the useEffect([]) can attach CodeMirror correctly.          ── */}
      <div className="flex-1 flex min-h-0">

        {/* Raw markdown editor */}
        <div ref={editorDivRef} className="flex-1 overflow-hidden border-r border-border" />

        {/* Live rendered preview */}
        <div className="flex-1 overflow-y-auto px-9 py-7">
          <div className="note-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content || ''}
            </ReactMarkdown>
          </div>
        </div>

      </div>
    </div>
  );
}
