import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { notesApi } from '@/api/notes';
import { ragApi } from '@/api/rag';
import { useUIStore } from '@/stores/ui';
import { t } from '@/i18n';
import type { NoteListItem } from '@/types/api';

type SearchMode = 'keyword' | 'semantic';

export default function SearchPanel() {
  const s = t();
  const { openTab } = useUIStore();
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<SearchMode>('keyword');
  const [submitted, setSubmitted] = useState('');

  // Keyword search
  const kwQuery = useQuery({
    queryKey: ['search-kw', submitted],
    queryFn: () => notesApi.search(submitted),
    enabled: mode === 'keyword' && submitted.length > 0,
  });

  // Semantic search
  const semQuery = useQuery({
    queryKey: ['search-sem', submitted],
    queryFn: async () => {
      const res = await ragApi.search({ query: submitted, limit: 10 });
      if (res.results.length === 0) return { items: [] };
      const ids = [...new Set(res.results.map((r) => r.note_id))];
      const batch = await notesApi.batch({ note_ids: ids });
      // sort by relevance
      return {
        items: ids.flatMap((id) => batch.items.filter((n) => n.id === id)),
      };
    },
    enabled: mode === 'semantic' && submitted.length > 0,
  });

  const activeQuery = mode === 'keyword' ? kwQuery : semQuery;
  const notes: NoteListItem[] = (activeQuery.data?.items ?? []) as NoteListItem[];

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) setSubmitted(query.trim());
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div
        className="flex-shrink-0 px-3 border-b border-border flex items-center"
        style={{ height: 'var(--tabbar-h)' }}
      >
        <span className="text-[12px] font-medium text-fg-muted uppercase tracking-wide">
          {s.notes.search}
        </span>
      </div>

      {/* Mode toggle + input */}
      <div className="flex-shrink-0 p-3 border-b border-border flex flex-col gap-2">
        <div className="flex gap-1">
          {(['keyword', 'semantic'] as SearchMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-2 py-0.5 rounded text-[11px] font-medium
                ${mode === m ? 'bg-bg-selected text-fg' : 'text-fg-muted hover:text-fg'}`}
            >
              {m === 'keyword' ? s.notes.search : s.notes.semanticSearch}
            </button>
          ))}
        </div>
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            className="flex-1 bg-bg-input border border-border rounded px-3 py-1.5 text-[13px] text-fg outline-none placeholder:text-fg-muted focus:border-border-focus"
            placeholder={mode === 'keyword' ? s.notes.searchPlaceholder : s.notes.semanticPlaceholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button
            type="submit"
            className="px-3 py-1.5 bg-accent text-white rounded text-[12px] font-medium hover:opacity-90"
          >
            →
          </button>
        </form>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto">
        {activeQuery.isLoading && (
          <div className="flex items-center justify-center h-24 text-fg-muted text-[12px]">
            {s.common.loading}
          </div>
        )}
        {!activeQuery.isLoading && submitted && notes.length === 0 && (
          <div className="flex items-center justify-center h-24 text-fg-muted text-[12px]">
            {s.notes.noResults}
          </div>
        )}
        {notes.map((note) => (
          <div
            key={note.id}
            className="px-3 py-2.5 border-b border-border/50 cursor-pointer hover:bg-bg-hover"
            onClick={() => openTab({ type: 'note', id: note.id })}
          >
            <div className="text-[13px] truncate">
              {note.title ?? <span className="text-fg-muted italic">{s.notes.untitled}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
