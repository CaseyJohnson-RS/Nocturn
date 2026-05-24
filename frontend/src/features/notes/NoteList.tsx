import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notesApi } from '@/api/notes';
import { useUIStore } from '@/stores/ui';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { t } from '@/i18n';
import type { NoteListItem } from '@/types/api';

function formatDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 86_400_000) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diff < 604_800_000) return d.toLocaleDateString([], { weekday: 'short' });
  return d.toLocaleDateString([], { day: 'numeric', month: 'short' });
}

export default function NoteList() {
  const s = t();
  const qc = useQueryClient();
  const { openTab, activeTabKey } = useUIStore();

  const [deleteTarget, setDeleteTarget] = useState<NoteListItem | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleteConfirm, setBatchDeleteConfirm] = useState(false);
  const [deletingBatch, setDeletingBatch] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['notes'],
    queryFn: () => notesApi.list({ limit: 200 }),
  });

  const createMut = useMutation({
    mutationFn: () => notesApi.create({ title: null, content: null }),
    onSuccess: (note) => {
      void qc.invalidateQueries({ queryKey: ['notes'] });
      useUIStore.getState().markEphemeral(note.id);
      openTab({ type: 'note', id: note.id });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => notesApi.delete(id),
    onSuccess: (_, id) => {
      useUIStore.getState().closeTab({ type: 'note', id });
      void qc.invalidateQueries({ queryKey: ['notes'] });
      void qc.invalidateQueries({ queryKey: ['notes-trash'] });
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

  function clearSelection() {
    setSelectedIds(new Set());
  }

  async function handleBatchDelete() {
    setDeletingBatch(true);
    const ids = Array.from(selectedIds);
    await Promise.allSettled(ids.map((id) => notesApi.delete(id)));
    ids.forEach((id) => useUIStore.getState().closeTab({ type: 'note', id }));
    void qc.invalidateQueries({ queryKey: ['notes'] });
    void qc.invalidateQueries({ queryKey: ['notes-trash'] });
    clearSelection();
    setBatchDeleteConfirm(false);
    setDeletingBatch(false);
  }

  const notes = data?.items ?? [];
  const hasSelection = selectedIds.size > 0;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div
        className="flex-shrink-0 flex items-center justify-between border-b border-border"
        style={{ height: '48px', padding: '0 16px' }}
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
              {s.notes.notes}
            </span>
            <button
              className="flex items-center gap-1.5 text-[12px] text-fg-muted hover:text-fg hover:bg-bg-hover rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ padding: '7px 14px' }}
              onClick={() => createMut.mutate()}
              disabled={createMut.isPending}
              title={s.notes.newNote}
            >
              {createMut.isPending ? (
                <span className="inline-block w-3 h-3 border-2 border-fg-disabled border-t-fg rounded-full animate-spin" />
              ) : (
                <>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                  {s.notes.newNote}
                </>
              )}
            </button>
          </>
        )}
      </div>

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
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <span className="text-[13px]">{s.notes.noNotes}</span>
            <button
              className="flex items-center gap-1.5 text-[12px] text-fg-muted hover:text-fg border border-border hover:border-border-focus rounded transition-colors"
              style={{ padding: '9px 20px' }}
              onClick={() => createMut.mutate()}
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              {s.notes.newNote}
            </button>
          </div>
        )}

        {notes.map((note) => {
          const key = `note:${note.id}`;
          const isActive = activeTabKey === key;
          return (
            <NoteRow
              key={note.id}
              note={note}
              active={isActive}
              selected={selectedIds.has(note.id)}
              onClick={() => openTab({ type: 'note', id: note.id })}
              onDelete={() => setDeleteTarget(note)}
              onToggle={() => toggleSelect(note.id)}
            />
          );
        })}
      </div>

      {/* Single delete confirm */}
      {deleteTarget && (
        <ConfirmDialog
          title={s.notes.delete}
          message={s.notes.deleteConfirm.replace('{title}', deleteTarget.title ?? s.notes.untitled)}
          confirmLabel={s.notes.delete}
          danger
          loading={deleteMut.isPending}
          onConfirm={() => deleteMut.mutate(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {/* Batch delete confirm */}
      {batchDeleteConfirm && (
        <ConfirmDialog
          title={s.notes.delete}
          message={s.notes.deleteMultipleConfirm.replace('{count}', String(selectedIds.size))}
          confirmLabel={s.notes.delete}
          danger
          loading={deletingBatch}
          onConfirm={() => void handleBatchDelete()}
          onCancel={() => setBatchDeleteConfirm(false)}
        />
      )}
    </div>
  );
}

interface NoteRowProps {
  note: NoteListItem;
  active: boolean;
  selected: boolean;
  onClick: () => void;
  onDelete: () => void;
  onToggle: () => void;
}

function NoteRow({ note, active, selected, onClick, onDelete, onToggle }: NoteRowProps) {
  const s = t();

  return (
    <div
      className={`group relative flex items-center gap-3 cursor-pointer border-b border-border/40
        ${selected ? '' : active ? 'bg-bg-selected' : 'hover:bg-bg-hover'}`}
      style={{
        padding: '10px 16px 10px 14px',
        background: selected ? 'rgba(0,122,204,0.10)' : undefined,
      }}
      onClick={onClick}
    >
      {/* Active accent bar */}
      {active && !selected && (
        <div className="absolute left-0 inset-y-0 w-[2px] rounded-r bg-accent" />
      )}

      {/* Checkbox */}
      <button
        className="flex-shrink-0 flex items-center justify-center rounded transition-colors"
        style={{
          width: '15px', height: '15px',
          marginTop: '1px',
          border: selected ? 'none' : '1.5px solid var(--color-fg-disabled)',
          background: selected ? 'var(--color-accent)' : 'transparent',
        }}
        onClick={(e) => { e.stopPropagation(); onToggle(); }}
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
        <div
          className="text-[13px] font-medium truncate leading-snug"
          style={{ color: active && !selected ? '#ffffff' : 'var(--color-fg)' }}
        >
          {note.title ?? (
            <span style={{
              color: active && !selected ? 'rgba(255,255,255,0.5)' : 'var(--color-fg-muted)',
              fontStyle: 'italic',
              fontWeight: 400,
            }}>
              {s.notes.untitled}
            </span>
          )}
        </div>

        {note.tags.length > 0 && (
          <div className="flex flex-wrap gap-1" style={{ marginTop: '8px' }}>
            {note.tags.map((tag) => (
              <span
                key={tag.id}
                className="text-[11px] leading-none rounded"
                style={{
                  padding: '2px 7px',
                  background: active && !selected ? 'rgba(255,255,255,0.12)' : 'var(--color-bg-input)',
                  color: active && !selected ? 'rgba(255,255,255,0.65)' : 'var(--color-fg-muted)',
                }}
              >
                #{tag.name}
              </span>
            ))}
          </div>
        )}

        <div
          className="text-[11px] leading-none"
          style={{
            marginTop: note.tags.length > 0 ? '6px' : '4px',
            color: active && !selected ? 'rgba(255,255,255,0.45)' : 'var(--color-fg-disabled)',
          }}
        >
          {formatDate(note.updated_at)}
        </div>
      </div>

      {/* Single-note delete — visible on hover */}
      <button
        className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded opacity-0 group-hover:opacity-100 hover:text-danger hover:bg-danger/10 transition-all"
        style={{ color: 'var(--color-fg-disabled)' }}
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        title={s.notes.delete}
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
          <path d="M10 11v6" /><path d="M14 11v6" />
          <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
        </svg>
      </button>
    </div>
  );
}
