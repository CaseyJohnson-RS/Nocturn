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
import { aiApi } from '@/api/ai';
import { isAxiosError } from '@/api/client';
import { useUIStore } from '@/stores/ui';
import type { TabId } from '@/stores/ui';
import { useChatStore } from '@/stores/chat';
import { t } from '@/i18n';
import { diffLines } from '@/utils/diff';
import type { DiffLine } from '@/utils/diff';
import type { NoteResponse, TagResponse, Proposal } from '@/types/api';

const AUTOSAVE_DELAY = 1500;
const TITLE_SAVE_DELAY = 400;

interface NoteEditorProps {
  noteId: string;
}

export default function NoteEditor({ noteId }: NoteEditorProps) {
  const s = t();
  const qc = useQueryClient();
  const { attachedNoteIds, attachNote, detachNote } = useUIStore();

  // ── Load note ──────────────────────────────────────────────────────────────
  const { data: note } = useQuery<NoteResponse>({
    queryKey: ['note', noteId],
    queryFn: () => notesApi.get(noteId),
    staleTime: Infinity,
  });

  const [title, setTitle] = useState(() => note?.title ?? '');
  const [content, setContent] = useState(() => note?.content ?? '');
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [tagSearch, setTagSearch] = useState('');
  const [tagFocused, setTagFocused] = useState(false);
  const [editorMode, setEditorMode] = useState<'editor' | 'split' | 'preview'>('split');
  const [isProcessingProposal, setIsProcessingProposal] = useState(false);
  const [isProcessingTagProposal, setIsProcessingTagProposal] = useState(false);
  const [isProcessingDeleteProposal, setIsProcessingDeleteProposal] = useState(false);

  const syncedNoteIdRef = useRef<string | null>(null);
  const versionRef = useRef<number>(note?.version ?? 1);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editorDivRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const programmaticUpdateRef = useRef(false);
  const titleRef = useRef(title);
  titleRef.current = title;
  const contentRef = useRef(content);
  contentRef.current = content;

  // ── Active edit proposal for this note ────────────────────────────────────
  const { messages, activeSessionId } = useChatStore();

  let activeProposal: Proposal | null = null;
  let proposalMessageId: string | null = null;
  for (const msg of messages) {
    for (const action of msg.actions ?? []) {
      if (
        action.type === 'proposal' &&
        (action as Proposal).proposal_type === 'edit_note' &&
        (action as Proposal).note_id === noteId &&
        (action as Proposal).status === 'pending'
      ) {
        activeProposal = action as Proposal;
        proposalMessageId = msg.id;
        break;
      }
    }
    if (activeProposal) break;
  }

  const proposedContent = (activeProposal?.data as { content?: string | null } | undefined)?.content ?? null;
  const proposedTitle   = (activeProposal?.data as { title?: string | null } | undefined)?.title ?? null;
  const isInDiffMode    = activeProposal !== null;

  const diffResult: DiffLine[] | null =
    isInDiffMode && proposedContent !== null
      ? diffLines(note?.content ?? '', proposedContent)
      : null;

  // ── Active tag proposals for this note ────────────────────────────────────
  const tagProposals: Array<{ proposal: Proposal; messageId: string }> = [];
  for (const msg of messages) {
    for (const action of msg.actions ?? []) {
      const p = action as Proposal;
      if (
        p.type === 'proposal' &&
        p.note_id === noteId &&
        p.status === 'pending' &&
        (p.proposal_type === 'add_tags' || p.proposal_type === 'remove_tags')
      ) {
        tagProposals.push({ proposal: p, messageId: msg.id });
      }
    }
  }

  const tagsToAdd: string[] = [];
  const tagsToRemove: string[] = [];
  for (const { proposal } of tagProposals) {
    const names = (proposal.data as { tags?: string[] } | undefined)?.tags ?? [];
    if (proposal.proposal_type === 'add_tags') tagsToAdd.push(...names);
    else tagsToRemove.push(...names);
  }
  const hasTagProposals = tagProposals.length > 0;

  // ── Active delete proposal for this note ──────────────────────────────────
  let deleteProposal: Proposal | null = null;
  let deleteProposalMessageId: string | null = null;
  for (const msg of messages) {
    for (const action of msg.actions ?? []) {
      const p = action as Proposal;
      if (
        p.type === 'proposal' &&
        p.note_id === noteId &&
        p.status === 'pending' &&
        p.proposal_type === 'delete_note'
      ) {
        deleteProposal = p;
        deleteProposalMessageId = msg.id;
        break;
      }
    }
    if (deleteProposal) break;
  }
  const isDeleteMode = deleteProposal !== null;

  // ── Sync note → local state on note switch ────────────────────────────────
  useEffect(() => {
    if (!note) return;
    versionRef.current = note.version;
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

  function scheduleSave(t2: string, c: string, delay = AUTOSAVE_DELAY) {
    useUIStore.getState().clearEphemeral(noteId);
    setDirty(true);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => void save(t2, c), delay);
  }

  // ── CodeMirror ─────────────────────────────────────────────────────────────
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
            if (update.docChanged && !programmaticUpdateRef.current) {
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
              padding: '24px 32px',
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

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const newDoc = note?.content ?? '';
    const current = view.state.doc.toString();
    if (current !== newDoc) {
      programmaticUpdateRef.current = true;
      view.dispatch({ changes: { from: 0, to: current.length, insert: newDoc } });
      programmaticUpdateRef.current = false;
    }
  }, [note?.id]);

  function handleTitleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter')
      editorDivRef.current?.querySelector<HTMLElement>('.cm-content')?.focus();
  }

  // ── Proposal accept / reject ───────────────────────────────────────────────
  async function handleProposalAction(status: 'applied' | 'dismissed') {
    if (!activeProposal || !proposalMessageId || !activeSessionId || isProcessingProposal) return;
    setIsProcessingProposal(true);
    try {
      const msg = await aiApi.updateAction(activeSessionId, proposalMessageId, activeProposal.id, { status });
      useChatStore.getState().replaceMessage(msg);
      if (status === 'applied') {
        // Apply changes to local editor immediately (server will confirm on refetch)
        if (proposedTitle !== null) setTitle(proposedTitle);
        if (proposedContent !== null) {
          setContent(proposedContent);
          const view = viewRef.current;
          if (view) {
            programmaticUpdateRef.current = true;
            view.dispatch({ changes: { from: 0, to: view.state.doc.toString().length, insert: proposedContent } });
            programmaticUpdateRef.current = false;
          }
        }
        // Reset sync ref so the refetch also syncs cleanly (titles, version)
        syncedNoteIdRef.current = null;
        void qc.invalidateQueries({ queryKey: ['note', noteId] });
        void qc.invalidateQueries({ queryKey: ['notes'] });
      }
    } catch { /* ignore */ }
    finally {
      setIsProcessingProposal(false);
    }
  }

  // ── Delete proposal accept / reject ──────────────────────────────────────
  async function handleDeleteProposalAction(status: 'applied' | 'dismissed') {
    if (!deleteProposal || !deleteProposalMessageId || !activeSessionId || isProcessingDeleteProposal) return;
    setIsProcessingDeleteProposal(true);
    try {
      const msg = await aiApi.updateAction(activeSessionId, deleteProposalMessageId, deleteProposal.id, { status });
      useChatStore.getState().replaceMessage(msg);
      if (status === 'applied') {
        useUIStore.getState().closeTab({ type: 'note', id: noteId } as TabId);
        void qc.invalidateQueries({ queryKey: ['notes'] });
        void qc.invalidateQueries({ queryKey: ['note', noteId] });
      }
    } catch { /* ignore */ }
    finally { setIsProcessingDeleteProposal(false); }
  }

  // ── Tag proposal accept / reject ─────────────────────────────────────────
  async function handleTagProposalAction(status: 'applied' | 'dismissed') {
    if (!activeSessionId || isProcessingTagProposal || tagProposals.length === 0) return;
    setIsProcessingTagProposal(true);
    // Group by messageId — sequential within same message to avoid backend races
    const byMessage = new Map<string, typeof tagProposals>();
    for (const p of tagProposals) {
      const group = byMessage.get(p.messageId) ?? [];
      group.push(p);
      byMessage.set(p.messageId, group);
    }
    try {
      await Promise.allSettled(
        Array.from(byMessage.values()).map(async (group) => {
          for (const { proposal, messageId } of group) {
            const msg = await aiApi.updateAction(activeSessionId, messageId, proposal.id, { status });
            useChatStore.getState().replaceMessage(msg);
          }
        })
      );
      if (status === 'applied') {
        void qc.invalidateQueries({ queryKey: ['note', noteId] });
        void qc.invalidateQueries({ queryKey: ['notes'] });
        void qc.invalidateQueries({ queryKey: ['tags'] });
      }
    } finally {
      setIsProcessingTagProposal(false);
    }
  }

  // ── Attach to chat ─────────────────────────────────────────────────────────
  const isAttached = attachedNoteIds.includes(noteId);
  const atLimit = attachedNoteIds.length >= 5;

  function handleAttach() {
    if (isAttached) detachNote(noteId);
    else if (!atLimit) attachNote(noteId);
  }

  // ── Sync save status to UIStore (for tab bar dot) ─────────────────────────
  useEffect(() => {
    const status = conflict ? 'conflict' : saving ? 'saving' : dirty ? 'dirty' : null;
    useUIStore.getState().setNoteTabStatus(noteId, status);
  }, [conflict, saving, dirty, noteId]);

  useEffect(() => () => { useUIStore.getState().setNoteTabStatus(noteId, null); }, [noteId]);

  // ── Delete ephemeral note on close if never edited ─────────────────────────
  useEffect(() => {
    return () => {
      if (useUIStore.getState().ephemeralNoteIds.has(noteId)) {
        useUIStore.getState().clearEphemeral(noteId);
        // Optimistically wipe from list cache so NoteList never shows it
        qc.setQueryData<{ items: Array<{ id: string }> }>(['notes'], (old) =>
          old ? { ...old, items: old.items.filter((n) => n.id !== noteId) } : old
        );
        // Delete on server, then re-sync to stay consistent
        notesApi.delete(noteId)
          .then(() => qc.invalidateQueries({ queryKey: ['notes'] }))
          .catch(() => qc.invalidateQueries({ queryKey: ['notes'] }));
      }
    };
  }, [noteId, qc]);

  // ── Save status dot ────────────────────────────────────────────────────────
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

      {/* ── Editor head: title + tags ── */}
      {note ? (
        <div className="flex-shrink-0 border-b border-border" style={{ padding: '20px 32px 14px' }}>
          {/* Title: normal or diff */}
          {isInDiffMode && proposedTitle !== null ? (
            <div style={{ marginBottom: '2px' }}>
              <div
                className="text-[20px] font-semibold leading-snug text-fg-muted"
                style={{ textDecoration: 'line-through', opacity: 0.5 }}
              >
                {title || s.notes.untitled}
              </div>
              <div className="text-[20px] font-semibold leading-snug" style={{ color: 'var(--color-success)' }}>
                {proposedTitle}
              </div>
            </div>
          ) : (
            <input
              className="w-full bg-transparent border-none outline-none text-[20px] font-semibold placeholder:text-fg-disabled leading-snug"
              style={{ color: isDeleteMode ? 'var(--color-danger)' : 'var(--color-fg)', opacity: isDeleteMode ? 0.7 : undefined }}
              placeholder={s.notes.untitled}
              value={title}
              disabled={isInDiffMode || isDeleteMode}
              onChange={(e) => {
                setTitle(e.target.value);
                qc.setQueryData<NoteResponse>(['note', noteId], (old) =>
                  old ? { ...old, title: e.target.value } : old,
                );
                scheduleSave(e.target.value, contentRef.current, TITLE_SAVE_DELAY);
              }}
              onKeyDown={handleTitleKeyDown}
            />
          )}

          <div className="flex flex-wrap items-center" style={{ marginTop: '12px', gap: '6px' }}>
            {/* Existing tags — red + strikethrough if being removed */}
            {note.tags.map((tag) => {
              const removing = tagsToRemove.some(
                (n) => n.toLowerCase() === tag.name.toLowerCase()
              );
              return (
                <span
                  key={tag.id}
                  className={`inline-flex items-center gap-1 rounded text-[12px] ${removing ? '' : 'bg-bg-input border border-border text-fg'}`}
                  style={{
                    padding: '3px 10px',
                    background: removing ? 'rgba(244,71,71,0.10)' : undefined,
                    border: removing ? '1px solid rgba(244,71,71,0.35)' : undefined,
                    color: removing ? 'var(--color-danger)' : undefined,
                    textDecoration: removing ? 'line-through' : undefined,
                    opacity: removing ? 0.75 : undefined,
                  }}
                >
                  #{tag.name}
                  {!hasTagProposals && !isDeleteMode && (
                    <button
                      className="text-fg-muted hover:text-danger text-[13px] leading-none"
                      onClick={() => removeTag(tag.id)}
                    >
                      ×
                    </button>
                  )}
                </span>
              );
            })}

            {/* Proposed new tags */}
            {tagsToAdd.map((tagName) => (
              <span
                key={`proposed-add-${tagName}`}
                className="inline-flex items-center rounded text-[12px]"
                style={{
                  padding: '3px 10px',
                  background: 'rgba(78,201,176,0.12)',
                  border: '1px solid var(--color-success)',
                  color: 'var(--color-success)',
                }}
              >
                +#{tagName}
              </span>
            ))}

            {/* Tag proposal accept / reject */}
            {hasTagProposals && (
              <div className="flex items-center gap-1.5" style={{ marginLeft: '2px' }}>
                <button
                  className="text-[11px] font-medium rounded border border-border text-fg-muted hover:text-danger hover:border-danger/50 hover:bg-danger/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{ padding: '2px 8px' }}
                  disabled={isProcessingTagProposal}
                  onClick={() => void handleTagProposalAction('dismissed')}
                >
                  {s.notes.rejectProposal}
                </button>
                <button
                  className="text-[11px] font-medium rounded border border-success/40 text-success bg-success/10 hover:bg-success/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{ padding: '2px 8px' }}
                  disabled={isProcessingTagProposal}
                  onClick={() => void handleTagProposalAction('applied')}
                >
                  {s.notes.acceptProposal}
                </button>
              </div>
            )}

            {/* Tag input — hidden while a tag proposal or delete proposal is active */}
            {!hasTagProposals && !isDeleteMode && (
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
            )}
          </div>
        </div>
      ) : (
        <div className="flex-shrink-0 border-b border-border" style={{ padding: '20px 32px 14px' }}>
          <div className="h-7 w-56 bg-bg-hover rounded animate-pulse" style={{ marginBottom: '12px' }} />
          <div className="h-4 w-28 bg-bg-hover rounded animate-pulse" />
        </div>
      )}

      {/* ── Toolbar ── */}
      <div
        className="flex-shrink-0 flex items-center justify-between border-b border-border"
        style={{ padding: '7px 32px', background: 'var(--color-bg-tab)' }}
      >
        {/* Left: mode toggle (always) + AI badge when in diff mode */}
        <div className="flex items-center gap-2">
          <div className="flex items-center" style={{ gap: '2px' }}>
            {([
              { mode: 'editor',  title: 'Editor only',
                icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> },
              { mode: 'split',   title: 'Split view',
                icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="9" height="18" rx="1"/><rect x="13" y="3" width="9" height="18" rx="1"/></svg> },
              { mode: 'preview', title: 'Preview only',
                icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> },
            ] as const).map(({ mode, title, icon }) => (
              <button
                key={mode}
                title={title}
                onClick={() => setEditorMode(mode)}
                className={`flex items-center justify-center rounded transition-colors ${
                  editorMode === mode
                    ? 'text-fg bg-bg-hover'
                    : 'text-fg-disabled hover:text-fg hover:bg-bg-hover'
                }`}
                style={{ width: '26px', height: '26px' }}
              >
                {icon}
              </button>
            ))}
          </div>
          {isInDiffMode && (
            <>
              <div className="w-px h-4 bg-border flex-shrink-0" />
              <span
                className="text-[10px] font-semibold uppercase tracking-widest"
                style={{ color: 'var(--color-accent)' }}
              >
                {s.notes.aiProposal}
              </span>
            </>
          )}
          {isDeleteMode && !isInDiffMode && (
            <>
              <div className="w-px h-4 bg-border flex-shrink-0" />
              <span
                className="text-[10px] font-semibold uppercase tracking-widest"
                style={{ color: 'var(--color-danger)' }}
              >
                {s.notes.aiDeleteProposal}
              </span>
            </>
          )}
        </div>

        {/* Right: proposal buttons or save status + attach */}
        {isInDiffMode ? (
          <div className="flex items-center gap-2">
            <button
              className="text-[12px] font-medium rounded border border-border text-fg-muted hover:text-danger hover:border-danger/50 hover:bg-danger/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ padding: '4px 12px' }}
              disabled={isProcessingProposal}
              onClick={() => void handleProposalAction('dismissed')}
            >
              {s.notes.rejectProposal}
            </button>
            <button
              className="text-[12px] font-medium rounded border border-success/40 text-success bg-success/10 hover:bg-success/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ padding: '4px 12px' }}
              disabled={isProcessingProposal}
              onClick={() => void handleProposalAction('applied')}
            >
              {s.notes.acceptProposal}
            </button>
          </div>
        ) : isDeleteMode ? (
          <div className="flex items-center gap-2">
            <button
              className="text-[12px] font-medium rounded border border-border text-fg-muted hover:text-fg hover:border-border-focus hover:bg-bg-hover transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ padding: '4px 12px' }}
              disabled={isProcessingDeleteProposal}
              onClick={() => void handleDeleteProposalAction('dismissed')}
            >
              {s.notes.rejectProposal}
            </button>
            <button
              className="text-[12px] font-medium rounded border border-danger/40 text-danger bg-danger/10 hover:bg-danger/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ padding: '4px 12px' }}
              disabled={isProcessingDeleteProposal}
              onClick={() => void handleDeleteProposalAction('applied')}
            >
              {s.notes.acceptProposal}
            </button>
          </div>
        ) : (
          <div className="flex items-center" style={{ gap: '10px' }}>
            {note && (
              <div className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotClass}`} />
                {dotLabel && (
                  <span className="text-[11px] text-fg-muted">{dotLabel}</span>
                )}
              </div>
            )}
            <button
              className={`text-[11px] rounded border transition-colors ${
                isAttached
                  ? 'border-accent text-accent bg-accent/10'
                  : atLimit
                  ? 'border-border text-fg-disabled cursor-not-allowed opacity-50'
                  : 'border-border text-fg-muted hover:text-fg hover:border-border-focus'
              }`}
              onClick={handleAttach}
              disabled={!isAttached && atLimit}
              title={!isAttached && atLimit ? s.notes.attachLimit : undefined}
              style={{ padding: '4px 10px' }}
            >
              📎 {isAttached ? s.notes.detachFromChat : s.notes.attachToChat}
            </button>
          </div>
        )}
      </div>

      {/* ── Delete proposal warning banner ── */}
      {isDeleteMode && (
        <div
          className="flex-shrink-0 flex items-center gap-2.5"
          style={{
            padding: '10px 32px',
            background: 'rgba(244,71,71,0.08)',
            borderBottom: '1px solid rgba(244,71,71,0.25)',
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" strokeWidth="2" style={{ flexShrink: 0 }}>
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
          <span className="text-[12px] font-medium" style={{ color: 'var(--color-danger)' }}>
            {s.notes.deleteProposalWarning}
          </span>
        </div>
      )}

      {/* ── Content area ── */}
      <div className="flex-1 flex min-h-0">

        {/* Left pane: CodeMirror (always mounted) overlaid by DiffView in diff mode */}
        <div
          style={{
            flex: editorMode === 'preview' ? '0 0 0%' : '1 1 0%',
            position: 'relative',
            overflow: 'hidden',
            borderRight: editorMode === 'split' ? '1px solid var(--color-border)' : 'none',
          }}
        >
          {/* CodeMirror — kept mounted at all times so the editor state is preserved */}
          <div
            ref={editorDivRef}
            style={{
              position: 'absolute',
              inset: 0,
              overflow: 'hidden',
              visibility: isInDiffMode ? 'hidden' : 'visible',
              pointerEvents: isInDiffMode || isDeleteMode ? 'none' : undefined,
            }}
          />
          {/* Diff view — sits on top of CM when a content proposal is active */}
          {isInDiffMode && (
            <div style={{ position: 'absolute', inset: 0, overflowY: 'auto', padding: '24px 32px' }}>
              {diffResult !== null ? (
                <DiffView lines={diffResult} />
              ) : (
                <span className="text-[13px] text-fg-muted italic">No content changes proposed.</span>
              )}
            </div>
          )}
          {/* Delete mode overlay — blocks editing, adds red tint */}
          {isDeleteMode && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                background: 'rgba(244,71,71,0.04)',
                pointerEvents: 'none',
              }}
            />
          )}
        </div>

        {/* Right pane: preview (proposed content in diff mode, current content otherwise) */}
        <div
          className="overflow-y-auto"
          style={{
            flex: editorMode === 'editor' ? '0 0 0%' : '1 1 0%',
            padding: editorMode !== 'editor' ? '24px 32px' : '0',
          }}
        >
          <div className="note-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {isInDiffMode ? (proposedContent ?? content) : content}
            </ReactMarkdown>
          </div>
        </div>

      </div>
    </div>
  );
}

// ── Diff view ──────────────────────────────────────────────────────────────────

function DiffView({ lines }: { lines: DiffLine[] }) {
  return (
    <div style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '13px', lineHeight: '1.6' }}>
      {lines.map((line, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            background:
              line.type === 'remove' ? 'rgba(244, 71, 71, 0.12)' :
              line.type === 'add'    ? 'rgba(78, 201, 176, 0.12)' :
              'transparent',
            borderLeft:
              line.type === 'remove' ? '3px solid var(--color-danger)' :
              line.type === 'add'    ? '3px solid var(--color-success)' :
              '3px solid transparent',
            padding: '1px 8px 1px 6px',
            userSelect: line.type === 'remove' ? 'none' : undefined,
            pointerEvents: line.type === 'remove' ? 'none' : undefined,
          }}
        >
          <span
            style={{
              flexShrink: 0,
              width: '16px',
              color:
                line.type === 'remove' ? 'var(--color-danger)' :
                line.type === 'add'    ? 'var(--color-success)' :
                'var(--color-fg-disabled)',
              userSelect: 'none',
            }}
          >
            {line.type === 'remove' ? '−' : line.type === 'add' ? '+' : ' '}
          </span>
          <span
            style={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              color:
                line.type === 'remove' ? 'var(--color-danger)' :
                line.type === 'add'    ? 'var(--color-success)' :
                'var(--color-fg)',
            }}
          >
            {line.text || ' '}
          </span>
        </div>
      ))}
    </div>
  );
}
