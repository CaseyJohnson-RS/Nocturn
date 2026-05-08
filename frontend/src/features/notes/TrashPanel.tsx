import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notesApi } from '@/api/notes';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { t } from '@/i18n';
import type { NoteListItem, NoteListResponse, NoteResponse } from '@/types/api';

function formatDeleted(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const daysLeft = 30 - Math.floor((now.getTime() - d.getTime()) / 86_400_000);
  return daysLeft > 0 ? daysLeft : 0;
}

export default function TrashPanel() {
  const s = t();
  const qc = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<NoteListItem | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleteConfirm, setBatchDeleteConfirm] = useState(false);
  const [batchRestoreConfirm, setBatchRestoreConfirm] = useState(false);
  const [processingBatch, setProcessingBatch] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['notes-trash'],
    queryFn: () => notesApi.list({ deleted: true, limit: 200 }),
  });

  const restoreMut = useMutation({
    mutationFn: (id: string) => notesApi.restore(id),
    onSuccess: (note: NoteResponse) => {
      // Immediately add to the notes list cache so NoteList shows it without waiting for a remount
      qc.setQueryData<NoteListResponse>(['notes'], (old) => {
        if (!old) return old;
        const item: NoteListItem = {
          id: note.id, title: note.title,
          updated_at: note.updated_at, deleted_at: null, tags: note.tags,
        };
        return { ...old, items: [item, ...old.items] };
      });
      // Remove from trash cache immediately
      qc.setQueryData<NoteListResponse>(['notes-trash'], (old) => {
        if (!old) return old;
        return { ...old, items: old.items.filter((n) => n.id !== note.id) };
      });
    },
  });

  const permDeleteMut = useMutation({
    mutationFn: (id: string) => notesApi.delete(id, true),
    onSuccess: (_, id: string) => {
      qc.setQueryData<NoteListResponse>(['notes-trash'], (old) => {
        if (!old) return old;
        return { ...old, items: old.items.filter((n) => n.id !== id) };
      });
      setDeleteTarget(null);
    },
  });

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function clearSelection() { setSelectedIds(new Set()); }

  async function handleBatchDelete() {
    setProcessingBatch(true);
    const ids = Array.from(selectedIds);
    await Promise.allSettled(ids.map((id) => notesApi.delete(id, true)));
    qc.setQueryData<NoteListResponse>(['notes-trash'], (old) => {
      if (!old) return old;
      const deleted = new Set(ids);
      return { ...old, items: old.items.filter((n) => !deleted.has(n.id)) };
    });
    clearSelection();
    setBatchDeleteConfirm(false);
    setProcessingBatch(false);
  }

  async function handleBatchRestore() {
    setProcessingBatch(true);
    const ids = Array.from(selectedIds);
    const results = await Promise.allSettled(ids.map((id) => notesApi.restore(id)));
    const restored = results
      .filter((r): r is PromiseFulfilledResult<NoteResponse> => r.status === 'fulfilled')
      .map((r) => r.value);
    // Add all successfully restored notes to the notes list cache
    qc.setQueryData<NoteListResponse>(['notes'], (old) => {
      if (!old) return old;
      const items = restored.map((note): NoteListItem => ({
        id: note.id, title: note.title,
        updated_at: note.updated_at, deleted_at: null, tags: note.tags,
      }));
      return { ...old, items: [...items, ...old.items] };
    });
    // Remove from trash
    const restoredIds = new Set(restored.map((n) => n.id));
    qc.setQueryData<NoteListResponse>(['notes-trash'], (old) => {
      if (!old) return old;
      return { ...old, items: old.items.filter((n) => !restoredIds.has(n.id)) };
    });
    clearSelection();
    setBatchRestoreConfirm(false);
    setProcessingBatch(false);
  }

  const notes = data?.items ?? [];
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
                className="flex items-center gap-1 text-[12px] rounded transition-colors disabled:opacity-40"
                style={{
                  padding: '5px 10px',
                  color: 'var(--color-fg-link)',
                  background: 'rgba(77,170,252,0.08)',
                  border: '1px solid rgba(77,170,252,0.25)',
                }}
                disabled={processingBatch}
                onClick={() => setBatchRestoreConfirm(true)}
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="1 4 1 10 7 10" />
                  <path d="M3.51 15a9 9 0 1 0 .49-4" />
                </svg>
                {s.notes.restore}
              </button>
              <button
                className="flex items-center gap-1 text-[12px] rounded transition-colors disabled:opacity-40"
                style={{
                  padding: '5px 10px',
                  color: 'var(--color-danger)',
                  background: 'rgba(244,71,71,0.08)',
                  border: '1px solid rgba(244,71,71,0.25)',
                }}
                disabled={processingBatch}
                onClick={() => setBatchDeleteConfirm(true)}
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                  <path d="M10 11v6" /><path d="M14 11v6" />
                  <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                </svg>
                {s.notes.deleteForever}
              </button>
              <button
                className="text-[12px] text-fg-muted hover:text-fg rounded transition-colors"
                style={{ padding: '5px 10px' }}
                onClick={clearSelection}
              >
                {s.common.cancel}
              </button>
            </div>
          </>
        ) : (
          <>
            <span className="text-[11px] font-semibold uppercase tracking-widest text-fg-disabled select-none">
              {s.notes.trash}
            </span>
            {notes.length > 0 && (
              <span
                className="text-[11px] leading-none rounded-full font-medium"
                style={{
                  padding: '3px 7px',
                  background: 'rgba(244,71,71,0.12)',
                  color: 'var(--color-danger)',
                  border: '1px solid rgba(244,71,71,0.25)',
                }}
              >
                {notes.length}
              </span>
            )}
          </>
        )}
      </div>

      {/* Hint bar */}
      {!hasSelection && (
        <div
          className="flex-shrink-0 flex items-center gap-1.5 border-b border-border text-fg-disabled"
          style={{ padding: '7px 16px' }}
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" className="flex-shrink-0">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span className="text-[11px]">{s.notes.trashHint}</span>
        </div>
      )}

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="flex items-center justify-center h-32 text-fg-muted text-[12px]">
            {s.common.loading}
          </div>
        )}

        {!isLoading && notes.length === 0 && (
          <div className="flex flex-col items-center justify-center h-48 gap-3 text-fg-disabled">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6" /><path d="M14 11v6" />
              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
            </svg>
            <span className="text-[13px]">{s.notes.trashEmpty}</span>
          </div>
        )}

        {notes.map((note) => (
          <TrashRow
            key={note.id}
            note={note}
            selected={selectedIds.has(note.id)}
            onToggleSelect={() => toggleSelect(note.id)}
            onRestore={() => restoreMut.mutate(note.id)}
            onDelete={() => setDeleteTarget(note)}
            restoring={restoreMut.variables === note.id && restoreMut.isPending}
          />
        ))}
      </div>

      {/* Single permanent delete confirm */}
      {deleteTarget && (
        <ConfirmDialog
          title={s.notes.deleteForever}
          message={s.notes.deleteForeverConfirm.replace(
            '{title}',
            deleteTarget.title ?? s.notes.untitled,
          )}
          confirmLabel={s.notes.deleteForever}
          danger
          loading={permDeleteMut.isPending}
          onConfirm={() => permDeleteMut.mutate(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {/* Batch permanent delete confirm */}
      {batchDeleteConfirm && (
        <ConfirmDialog
          title={s.notes.deleteForever}
          message={s.notes.deleteMultipleConfirm.replace('{count}', String(selectedIds.size))}
          confirmLabel={s.notes.deleteForever}
          danger
          loading={processingBatch}
          onConfirm={() => void handleBatchDelete()}
          onCancel={() => setBatchDeleteConfirm(false)}
        />
      )}

      {/* Batch restore confirm */}
      {batchRestoreConfirm && (
        <ConfirmDialog
          title={s.notes.restore}
          message={s.notes.restoreMultipleConfirm.replace('{count}', String(selectedIds.size))}
          confirmLabel={s.notes.restore}
          loading={processingBatch}
          onConfirm={() => void handleBatchRestore()}
          onCancel={() => setBatchRestoreConfirm(false)}
        />
      )}
    </div>
  );
}

// ── TrashRow ──────────────────────────────────────────────────────────────────

interface TrashRowProps {
  note: NoteListItem;
  selected: boolean;
  onToggleSelect: () => void;
  onRestore: () => void;
  onDelete: () => void;
  restoring: boolean;
}

function TrashRow({ note, selected, onToggleSelect, onRestore, onDelete, restoring }: TrashRowProps) {
  const s = t();
  const daysLeft = note.deleted_at ? formatDeleted(note.deleted_at) : null;

  return (
    <div
      className={`group relative flex items-center gap-3 border-b border-border/40 transition-colors
        ${selected ? '' : 'hover:bg-bg-hover'}`}
      style={{
        padding: '10px 16px 10px 14px',
        background: selected ? 'rgba(244,71,71,0.07)' : undefined,
      }}
    >
      {/* Checkbox */}
      <button
        className="flex-shrink-0 flex items-center justify-center rounded transition-colors"
        style={{
          width: '15px', height: '15px',
          marginTop: '1px',
          border: selected ? 'none' : '1.5px solid var(--color-fg-disabled)',
          background: selected ? 'var(--color-danger)' : 'transparent',
        }}
        onClick={onToggleSelect}
        tabIndex={-1}
      >
        {selected && (
          <svg width="9" height="9" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="1.75">
            <polyline points="1.5,5 4,7.5 8.5,2" />
          </svg>
        )}
      </button>

      {/* Text */}
      <div className="flex-1 min-w-0">
        <div className="text-[13px] truncate" style={{ color: 'var(--color-fg-muted)' }}>
          {note.title ?? (
            <span className="italic" style={{ color: 'var(--color-fg-disabled)' }}>
              {s.notes.untitled}
            </span>
          )}
        </div>
        {daysLeft !== null && (
          <div className="flex items-center gap-1 mt-0.5">
            <span
              className="text-[11px] leading-none"
              style={{ color: daysLeft <= 3 ? 'var(--color-danger)' : 'var(--color-fg-disabled)' }}
            >
              {daysLeft <= 3 && daysLeft > 0 ? `${daysLeft}d left` : daysLeft === 0 ? 'Expiring soon' : `${daysLeft}d left`}
            </span>
          </div>
        )}
      </div>

      {/* Right slot: actions (opacity-0 → opacity-100 on hover, no layout shift) */}
      <div className="flex-shrink-0 relative flex items-center justify-end" style={{ width: '68px', height: '28px' }}>
        <div
          className="absolute inset-0 flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <button
            className="w-7 h-7 flex items-center justify-center rounded transition-colors disabled:opacity-40"
            style={{ color: 'var(--color-fg-link)' }}
            onClick={onRestore}
            disabled={restoring}
            title={s.notes.restore}
          >
            {restoring ? (
              <span className="inline-block w-3.5 h-3.5 border-2 border-fg-disabled border-t-fg-link rounded-full animate-spin" />
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="1 4 1 10 7 10" />
                <path d="M3.51 15a9 9 0 1 0 .49-4" />
              </svg>
            )}
          </button>
          <button
            className="w-7 h-7 flex items-center justify-center rounded hover:bg-danger/10 transition-colors"
            style={{ color: 'var(--color-danger)' }}
            onClick={onDelete}
            title={s.notes.deleteForever}
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
    </div>
  );
}
