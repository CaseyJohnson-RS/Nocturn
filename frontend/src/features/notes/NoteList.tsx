import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notesApi } from '@/api/notes';
import { useUIStore } from '@/stores/ui';
import { Button } from '@/components/ui/Button';
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

  const { data, isLoading } = useQuery({
    queryKey: ['notes'],
    queryFn: () => notesApi.list({ limit: 200 }),
  });

  const createMut = useMutation({
    mutationFn: () => notesApi.create({ title: null, content: null }),
    onSuccess: (note) => {
      void qc.invalidateQueries({ queryKey: ['notes'] });
      openTab({ type: 'note', id: note.id });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => notesApi.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notes'] });
      setDeleteTarget(null);
    },
  });

  const notes = data?.items ?? [];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div
        className="flex-shrink-0 flex items-center justify-between px-3 border-b border-border"
        style={{ height: 'var(--tabbar-h)' }}
      >
        <span className="text-[12px] font-medium text-fg-muted uppercase tracking-wide">
          {s.notes.notes}
        </span>
        <Button size="sm" variant="ghost" onClick={() => createMut.mutate()} loading={createMut.isPending}>
          + {s.notes.newNote}
        </Button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="flex items-center justify-center h-32 text-fg-muted text-[12px]">
            {s.common.loading}
          </div>
        )}

        {!isLoading && notes.length === 0 && (
          <div className="flex flex-col items-center justify-center h-48 gap-3 text-fg-muted">
            <span className="text-3xl">📝</span>
            <span className="text-[13px]">{s.notes.noNotes}</span>
            <Button size="sm" onClick={() => createMut.mutate()}>
              {s.notes.newNote}
            </Button>
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
              onClick={() => openTab({ type: 'note', id: note.id })}
              onDelete={() => setDeleteTarget(note)}
            />
          );
        })}
      </div>

      {deleteTarget && (
        <ConfirmDialog
          title={s.notes.delete}
          message={s.notes.deleteConfirm.replace(
            '{title}',
            deleteTarget.title ?? s.notes.untitled,
          )}
          confirmLabel={s.notes.delete}
          danger
          loading={deleteMut.isPending}
          onConfirm={() => deleteMut.mutate(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

interface NoteRowProps {
  note: NoteListItem;
  active: boolean;
  onClick: () => void;
  onDelete: () => void;
}

function NoteRow({ note, active, onClick, onDelete }: NoteRowProps) {
  const s = t();
  const [hover, setHover] = useState(false);

  return (
    <div
      className={`group flex items-center px-3 py-2.5 cursor-pointer border-b border-border/50 gap-2
        ${active ? 'bg-bg-selected' : 'hover:bg-bg-hover'}`}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div className="flex-1 min-w-0">
        <div className="text-[13px] truncate">
          {note.title ?? <span className="text-fg-muted italic">{s.notes.untitled}</span>}
        </div>
        <div className="text-[11px] text-fg-muted mt-0.5">
          {s.notes.updatedAt} {formatDate(note.updated_at)}
        </div>
      </div>
      {hover && (
        <button
          className="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded text-fg-muted hover:text-danger hover:bg-danger/10 text-[14px]"
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          title={s.notes.delete}
        >
          🗑
        </button>
      )}
    </div>
  );
}
