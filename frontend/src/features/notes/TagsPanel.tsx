import { useState, useRef, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tagsApi } from '@/api/tags';
import { notesApi } from '@/api/notes';
import { isAxiosError } from '@/api/client';
import { useUIStore } from '@/stores/ui';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { t } from '@/i18n';
import type { TagResponse, TagListResponse } from '@/types/api';

function formatDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 86_400_000) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diff < 604_800_000) return d.toLocaleDateString([], { weekday: 'short' });
  return d.toLocaleDateString([], { day: 'numeric', month: 'short' });
}

export default function TagsPanel() {
  const s = t();
  const qc = useQueryClient();
  const { openTab, expandedTagIds, toggleExpandedTag } = useUIStore();

  const [addingNew, setAddingNew] = useState(false);
  const [newTagName, setNewTagName] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<TagResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleteConfirm, setBatchDeleteConfirm] = useState(false);
  const [deletingBatch, setDeletingBatch] = useState(false);
  const newInputRef = useRef<HTMLInputElement>(null);
  // Prevents onBlur double-fire when the input unmounts after a successful submit
  const submittingRef = useRef(false);

  useEffect(() => {
    if (addingNew) newInputRef.current?.focus();
  }, [addingNew]);

  const { data } = useQuery({
    queryKey: ['tags'],
    queryFn: () => tagsApi.list({ limit: 100 }),
  });

  // Reuse the same cache key as NoteList — free cache hit when NoteList has run
  const { data: notesData } = useQuery({
    queryKey: ['notes'],
    queryFn: () => notesApi.list({ limit: 200 }),
  });

  const tagNoteCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const note of notesData?.items ?? []) {
      for (const tag of note.tags) {
        counts[tag.id] = (counts[tag.id] ?? 0) + 1;
      }
    }
    return counts;
  }, [notesData]);

  const createMut = useMutation({
    mutationFn: (name: string) => tagsApi.create({ name }),
    onSuccess: (tag) => {
      qc.setQueryData<TagListResponse>(['tags'], (old) =>
        old ? { ...old, items: [...old.items, tag] } : old,
      );
      setNewTagName('');
      setAddingNew(false);
      setCreateError(null);
    },
    onError: (err) => {
      submittingRef.current = false;
      setCreateError(
        isAxiosError(err) && err.response?.status === 409
          ? s.tags.tagExists
          : s.common.error,
      );
    },
  });

  const renameMut = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => tagsApi.update(id, { name }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['tags'] });
      setEditingId(null);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => tagsApi.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['tags'] });
      void qc.invalidateQueries({ queryKey: ['notes'] });
      setDeleteTarget(null);
    },
  });

  const expandedList = Array.from(expandedTagIds);

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function clearSelection() { setSelectedIds(new Set()); }

  async function handleBatchDelete() {
    setDeletingBatch(true);
    const ids = Array.from(selectedIds);
    await Promise.allSettled(ids.map((id) => tagsApi.delete(id)));
    void qc.invalidateQueries({ queryKey: ['tags'] });
    void qc.invalidateQueries({ queryKey: ['notes'] });
    clearSelection();
    setBatchDeleteConfirm(false);
    setDeletingBatch(false);
  }

  function submitNew() {
    if (submittingRef.current) return;
    const name = newTagName.trim();
    if (!name) {
      setAddingNew(false);
      setNewTagName('');
      setCreateError(null);
      return;
    }
    submittingRef.current = true;
    setCreateError(null);
    createMut.mutate(name);
  }

  const tags = data?.items ?? [];
  const hasSelection = selectedIds.size > 0;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div
        className="flex-shrink-0 flex items-center justify-between border-b border-border"
        style={{ height: '40px', padding: '0 16px' }}
      >
        {hasSelection ? (
          <>
            <span className="text-[11px] font-medium text-fg-muted select-none">
              {s.notes.selected.replace('{count}', String(selectedIds.size))}
            </span>
            <div className="flex items-center gap-1.5">
              <button
                className="flex items-center gap-1 text-[12px] rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                style={{
                  padding: '5px 12px',
                  color: 'var(--color-danger)',
                  background: 'rgba(244,71,71,0.08)',
                  border: '1px solid rgba(244,71,71,0.25)',
                }}
                disabled={deletingBatch}
                onClick={() => setBatchDeleteConfirm(true)}
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                  <path d="M10 11v6" /><path d="M14 11v6" />
                  <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                </svg>
                {s.notes.delete} {selectedIds.size}
              </button>
              <button
                className="text-[12px] text-fg-muted hover:text-fg rounded transition-colors"
                style={{ padding: '5px 12px' }}
                onClick={clearSelection}
              >
                {s.common.cancel}
              </button>
            </div>
          </>
        ) : (
          <>
            <span className="text-[11px] font-semibold uppercase tracking-widest text-fg-disabled select-none">
              {s.notes.tags}
            </span>
            <button
              className="flex items-center gap-1.5 text-[12px] text-fg-muted hover:text-fg hover:bg-bg-hover rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ padding: '5px 12px' }}
              onClick={() => { submittingRef.current = false; setCreateError(null); setAddingNew(true); }}
              disabled={addingNew || createMut.isPending}
              title={s.notes.newTag}
            >
              {createMut.isPending ? (
                <span className="inline-block w-3 h-3 border-2 border-fg-disabled border-t-fg rounded-full animate-spin" />
              ) : (
                <>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                  {s.notes.newTag}
                </>
              )}
            </button>
          </>
        )}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">

        {/* Inline new-tag input row */}
        {addingNew && (
          <div className="border-b border-border/40">
            <div
              className="flex items-center gap-2"
              style={{ padding: '10px 16px 10px 14px' }}
            >
              <span style={{ width: '15px', flexShrink: 0 }} />
              <span className="text-[13px] text-fg-muted select-none flex-shrink-0">#</span>
              <input
                ref={newInputRef}
                className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-fg-disabled"
                style={{ color: createError ? 'var(--color-danger)' : 'var(--color-fg)' }}
                placeholder={s.notes.tagPlaceholder}
                value={newTagName}
                onChange={(e) => { setNewTagName(e.target.value); setCreateError(null); }}
                maxLength={50}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') submitNew();
                  if (e.key === 'Escape') { setAddingNew(false); setNewTagName(''); setCreateError(null); }
                }}
                onBlur={submitNew}
              />
            </div>
            {createError && (
              <div
                className="flex items-center gap-1 text-[11px]"
                style={{ padding: '0 16px 7px 46px', color: 'var(--color-danger)' }}
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                {createError}
              </div>
            )}
          </div>
        )}

        {/* Empty state */}
        {tags.length === 0 && !addingNew && (
          <div className="flex flex-col items-center justify-center h-48 gap-3 text-fg-disabled">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25">
              <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
              <line x1="7" y1="7" x2="7.01" y2="7" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
            <span className="text-[13px]">{s.tags.noTags}</span>
          </div>
        )}

        {/* Tag rows */}
        {tags.map((tag) => (
          <TagRow
            key={tag.id}
            tag={tag}
            noteCount={tagNoteCounts[tag.id] ?? 0}
            isExpanded={expandedTagIds.has(tag.id)}
            isSelected={selectedIds.has(tag.id)}
            isEditing={editingId === tag.id}
            editName={editName}
            expandedList={expandedList}
            onToggleExpand={() => toggleExpandedTag(tag.id)}
            onToggleSelect={() => toggleSelect(tag.id)}
            onStartEdit={() => { setEditingId(tag.id); setEditName(tag.name); }}
            onEditChange={(v) => setEditName(v)}
            onEditCommit={() => {
              if (editName.trim() && editName !== tag.name) {
                renameMut.mutate({ id: tag.id, name: editName.trim() });
              } else {
                setEditingId(null);
              }
            }}
            onEditCancel={() => setEditingId(null)}
            onDelete={() => setDeleteTarget(tag)}
            onOpenNote={(id) => openTab({ type: 'note', id })}
            strings={s}
          />
        ))}
      </div>

      {deleteTarget && (
        <ConfirmDialog
          title={s.tags.deleteTag}
          message={s.tags.deleteTagConfirm.replace('{name}', deleteTarget.name)}
          confirmLabel={s.tags.deleteTag}
          danger
          loading={deleteMut.isPending}
          onConfirm={() => deleteMut.mutate(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {batchDeleteConfirm && (
        <ConfirmDialog
          title={s.tags.deleteTag}
          message={s.tags.deleteMultipleConfirm.replace('{count}', String(selectedIds.size))}
          confirmLabel={s.tags.deleteTag}
          danger
          loading={deletingBatch}
          onConfirm={() => void handleBatchDelete()}
          onCancel={() => setBatchDeleteConfirm(false)}
        />
      )}
    </div>
  );
}

// ── TagRow ────────────────────────────────────────────────────────────────────

interface TagRowProps {
  tag: TagResponse;
  noteCount: number;
  isExpanded: boolean;
  isSelected: boolean;
  isEditing: boolean;
  editName: string;
  expandedList: string[];
  onToggleExpand: () => void;
  onToggleSelect: () => void;
  onStartEdit: () => void;
  onEditChange: (v: string) => void;
  onEditCommit: () => void;
  onEditCancel: () => void;
  onDelete: () => void;
  onOpenNote: (id: string) => void;
  strings: ReturnType<typeof t>;
}

function TagRow({
  tag, noteCount, isExpanded, isSelected, isEditing, editName, expandedList,
  onToggleExpand, onToggleSelect, onStartEdit,
  onEditChange, onEditCommit, onEditCancel,
  onDelete, onOpenNote, strings: s,
}: TagRowProps) {
  const qc = useQueryClient();

  const { data: tagNotes } = useQuery({
    queryKey: ['notes-by-tag', tag.id],
    queryFn: () => notesApi.list({ tag_ids: tag.id, limit: 50 }),
    enabled: expandedList.includes(tag.id),
    staleTime: 30_000,
  });

  function prefetch() {
    void qc.prefetchQuery({
      queryKey: ['notes-by-tag', tag.id],
      queryFn: () => notesApi.list({ tag_ids: tag.id, limit: 50 }),
      staleTime: 30_000,
    });
  }

  const notes = tagNotes?.items ?? [];

  return (
    <div className="border-b border-border/40">
      {/* Tag row */}
      <div
        className={`group relative flex items-center gap-2 cursor-pointer transition-colors
          ${isSelected ? '' : isExpanded ? 'bg-bg-hover' : 'hover:bg-bg-hover'}`}
        style={{
          padding: '10px 16px 10px 14px',
          background: isSelected ? 'rgba(0,122,204,0.10)' : undefined,
        }}
        onClick={onToggleExpand}
        onMouseEnter={prefetch}
      >
        {/* Checkbox */}
        <button
          className="flex-shrink-0 flex items-center justify-center rounded transition-colors"
          style={{
            width: '15px', height: '15px',
            marginTop: '1px',
            border: isSelected ? 'none' : '1.5px solid var(--color-fg-disabled)',
            background: isSelected ? 'var(--color-accent)' : 'transparent',
          }}
          onClick={(e) => { e.stopPropagation(); onToggleSelect(); }}
          tabIndex={-1}
        >
          {isSelected && (
            <svg width="9" height="9" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="1.75">
              <polyline points="1.5,5 4,7.5 8.5,2" />
            </svg>
          )}
        </button>

        {/* Expand chevron */}
        <svg
          className="flex-shrink-0 text-fg-disabled transition-transform duration-150"
          style={{ transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)' }}
          width="10" height="10" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" strokeWidth="2.5"
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>

        {/* # prefix */}
        <span className="text-[13px] text-fg-muted select-none flex-shrink-0">#</span>

        {/* Name or edit input */}
        {isEditing ? (
          <input
            autoFocus
            className="flex-1 bg-transparent text-[13px] text-fg outline-none"
            value={editName}
            onChange={(e) => onEditChange(e.target.value)}
            onBlur={onEditCommit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') e.currentTarget.blur();
              if (e.key === 'Escape') onEditCancel();
            }}
            onClick={(e) => e.stopPropagation()}
            maxLength={50}
          />
        ) : (
          <span className="flex-1 text-[13px] truncate">{tag.name}</span>
        )}

        {/* Right slot: badge fades out on hover, actions fade in — same width, no layout shift */}
        {!isEditing && (
          <div className="flex-shrink-0 relative flex items-center justify-end" style={{ width: '60px', height: '28px' }}>
            {/* Note count badge */}
            <span
              className="absolute inset-0 flex items-center justify-end group-hover:opacity-0 transition-opacity pointer-events-none select-none"
            >
              <span
                className="text-[11px] leading-none rounded-full font-medium"
                style={{
                  padding: '3px 7px',
                  background: 'rgba(0,122,204,0.18)',
                  color: '#4daafc',
                  border: '1px solid rgba(0,122,204,0.30)',
                }}
              >
                {noteCount}
              </span>
            </span>

            {/* Action buttons */}
            <div
              className="absolute inset-0 flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                className="w-7 h-7 flex items-center justify-center rounded text-fg-disabled hover:text-fg hover:bg-bg-input transition-colors"
                onClick={onStartEdit}
                title={s.tags.rename}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              </button>
              <button
                className="w-7 h-7 flex items-center justify-center rounded text-fg-disabled hover:text-danger hover:bg-danger/10 transition-colors"
                onClick={onDelete}
                title={s.tags.deleteTag}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                  <path d="M10 11v6" /><path d="M14 11v6" />
                  <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Expanded: notes under this tag */}
      {isExpanded && (
        <div className="border-t border-border/30">
          {notes.length === 0 ? (
            <div
              className="text-[12px] text-fg-disabled italic"
              style={{ padding: '8px 16px 8px 46px' }}
            >
              {s.notes.noNotes}
            </div>
          ) : (
            notes.map((note) => (
              <div
                key={note.id}
                className="flex items-center gap-2 cursor-pointer hover:bg-bg-hover transition-colors border-b border-border/20 last:border-b-0"
                style={{ padding: '7px 16px 7px 46px' }}
                onClick={() => onOpenNote(note.id)}
              >
                <svg className="flex-shrink-0 text-fg-disabled" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <span className="text-[12px] text-fg-muted truncate flex-1">
                  {note.title ?? (
                    <span className="italic text-fg-disabled">{s.notes.untitled}</span>
                  )}
                </span>
                <span className="text-[11px] text-fg-disabled flex-shrink-0">
                  {formatDate(note.updated_at)}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
