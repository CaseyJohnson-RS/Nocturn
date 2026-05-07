import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notesApi } from '@/api/notes';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { t } from '@/i18n';
import type { NoteListItem } from '@/types/api';

export default function TrashPanel() {
  const s = t();
  const qc = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<NoteListItem | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['notes-trash'],
    queryFn: () => notesApi.list({ deleted: true, limit: 200 }),
  });

  const restoreMut = useMutation({
    mutationFn: (id: string) => notesApi.restore(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notes'] });
      void qc.invalidateQueries({ queryKey: ['notes-trash'] });
    },
  });

  const permDeleteMut = useMutation({
    mutationFn: (id: string) => notesApi.delete(id, true),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notes-trash'] });
      setDeleteTarget(null);
    },
  });

  const notes = data?.items ?? [];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div
        className="flex-shrink-0 flex items-center px-3 border-b border-border"
        style={{ height: 'var(--tabbar-h)' }}
      >
        <span className="text-[12px] font-medium text-fg-muted uppercase tracking-wide">
          {s.notes.trash}
        </span>
      </div>

      {/* Hint */}
      <div className="flex-shrink-0 px-3 py-2 border-b border-border text-[11px] text-fg-muted">
        {s.notes.trashHint}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="flex items-center justify-center h-24 text-fg-muted text-[12px]">
            {s.common.loading}
          </div>
        )}
        {!isLoading && notes.length === 0 && (
          <div className="flex flex-col items-center justify-center h-48 gap-2 text-fg-muted">
            <span className="text-3xl">🗑</span>
            <span className="text-[13px]">{s.notes.trashEmpty}</span>
          </div>
        )}
        {notes.map((note) => (
          <TrashRow
            key={note.id}
            note={note}
            onRestore={() => restoreMut.mutate(note.id)}
            onDelete={() => setDeleteTarget(note)}
            restoring={restoreMut.isPending}
          />
        ))}
      </div>

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
    </div>
  );
}

interface TrashRowProps {
  note: NoteListItem;
  onRestore: () => void;
  onDelete: () => void;
  restoring: boolean;
}

function TrashRow({ note, onRestore, onDelete, restoring }: TrashRowProps) {
  const s = t();
  return (
    <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border/50 hover:bg-bg-hover group">
      <div className="flex-1 min-w-0">
        <div className="text-[13px] truncate text-fg-muted">
          {note.title ?? <span className="italic">{s.notes.untitled}</span>}
        </div>
        {note.deleted_at && (
          <div className="text-[11px] text-fg-disabled mt-0.5">
            {new Date(note.deleted_at).toLocaleDateString()}
          </div>
        )}
      </div>
      <div className="hidden group-hover:flex items-center gap-1">
        <button
          className="text-[11px] px-2 py-0.5 rounded text-fg-link hover:bg-fg-link/10"
          onClick={onRestore}
          disabled={restoring}
        >
          {s.notes.restore}
        </button>
        <button
          className="text-[11px] px-2 py-0.5 rounded text-danger hover:bg-danger/10"
          onClick={onDelete}
        >
          {s.notes.deleteForever}
        </button>
      </div>
    </div>
  );
}
