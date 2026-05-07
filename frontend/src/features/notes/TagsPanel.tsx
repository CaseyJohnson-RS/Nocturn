import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tagsApi } from '@/api/tags';
import { notesApi } from '@/api/notes';
import { useUIStore } from '@/stores/ui';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { t } from '@/i18n';
import type { TagResponse } from '@/types/api';

export default function TagsPanel() {
  const s = t();
  const qc = useQueryClient();
  const { openTab } = useUIStore();

  const [newTagName, setNewTagName] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<TagResponse | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ['tags'],
    queryFn: () => tagsApi.list({ limit: 100 }),
  });

  const createMut = useMutation({
    mutationFn: (name: string) => tagsApi.create({ name }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['tags'] }); setNewTagName(''); },
  });

  const renameMut = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => tagsApi.update(id, { name }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['tags'] }); setEditingId(null); },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => tagsApi.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['tags'] });
      void qc.invalidateQueries({ queryKey: ['notes'] });
      setDeleteTarget(null);
    },
  });

  const { data: tagNotes } = useQuery({
    queryKey: ['notes-by-tag', expandedId],
    queryFn: () => notesApi.list({ tag_ids: expandedId!, limit: 50 }),
    enabled: !!expandedId,
  });

  const tags = data?.items ?? [];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div
        className="flex-shrink-0 flex items-center justify-between px-3 border-b border-border"
        style={{ height: 'var(--tabbar-h)' }}
      >
        <span className="text-[12px] font-medium text-fg-muted uppercase tracking-wide">
          {s.notes.tags}
        </span>
      </div>

      {/* New tag input */}
      <div className="flex-shrink-0 p-3 border-b border-border">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (newTagName.trim()) createMut.mutate(newTagName.trim());
          }}
        >
          <input
            className="flex-1 bg-bg-input border border-border rounded px-2.5 py-1.5 text-[13px] text-fg outline-none placeholder:text-fg-muted focus:border-border-focus"
            placeholder={s.notes.tagPlaceholder}
            value={newTagName}
            onChange={(e) => setNewTagName(e.target.value)}
            maxLength={50}
          />
          <button
            type="submit"
            className="px-3 bg-accent text-white rounded text-[12px] font-medium hover:opacity-90"
            disabled={createMut.isPending}
          >
            +
          </button>
        </form>
      </div>

      {/* Tags list */}
      <div className="flex-1 overflow-y-auto">
        {tags.length === 0 && (
          <div className="flex items-center justify-center h-24 text-fg-muted text-[12px]">
            {s.tags.noTags}
          </div>
        )}

        {tags.map((tag) => (
          <div key={tag.id} className="border-b border-border/50">
            {/* Tag row */}
            <div
              className="flex items-center gap-2 px-3 py-2 hover:bg-bg-hover group cursor-pointer"
              onClick={() => setExpandedId(expandedId === tag.id ? null : tag.id)}
            >
              <span className="text-fg-muted text-[13px]">#</span>
              {editingId === tag.id ? (
                <input
                  autoFocus
                  className="flex-1 bg-bg-input border border-border-focus rounded px-1.5 py-0.5 text-[13px] text-fg outline-none"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onBlur={() => {
                    if (editName.trim() && editName !== tag.name) {
                      renameMut.mutate({ id: tag.id, name: editName.trim() });
                    } else {
                      setEditingId(null);
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') e.currentTarget.blur();
                    if (e.key === 'Escape') setEditingId(null);
                  }}
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <span className="flex-1 text-[13px] truncate">{tag.name}</span>
              )}

              {/* Actions */}
              <div
                className="hidden group-hover:flex items-center gap-1"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  className="text-fg-muted hover:text-fg text-[11px] px-1.5 py-0.5 rounded hover:bg-bg-input"
                  onClick={() => { setEditingId(tag.id); setEditName(tag.name); }}
                  title={s.tags.rename}
                >
                  ✏
                </button>
                <button
                  className="text-fg-muted hover:text-danger text-[11px] px-1.5 py-0.5 rounded hover:bg-danger/10"
                  onClick={() => setDeleteTarget(tag)}
                  title={s.tags.deleteTag}
                >
                  🗑
                </button>
              </div>
            </div>

            {/* Expanded notes */}
            {expandedId === tag.id && (
              <div className="bg-bg-card border-t border-border/30">
                {(tagNotes?.items ?? []).map((note) => (
                  <div
                    key={note.id}
                    className="pl-6 pr-3 py-1.5 text-[12px] text-fg-muted hover:text-fg hover:bg-bg-hover cursor-pointer truncate"
                    onClick={() => openTab({ type: 'note', id: note.id })}
                  >
                    📄 {note.title ?? <span className="italic">{t().notes.untitled}</span>}
                  </div>
                ))}
                {(tagNotes?.items ?? []).length === 0 && (
                  <div className="pl-6 py-1.5 text-[11px] text-fg-disabled">
                    {s.notes.noNotes}
                  </div>
                )}
              </div>
            )}
          </div>
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
    </div>
  );
}
