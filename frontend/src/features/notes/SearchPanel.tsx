import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { notesApi } from '@/api/notes';
import { ragApi } from '@/api/rag';
import { useUIStore } from '@/stores/ui';
import { t } from '@/i18n';
import type { NoteListItem, SearchResult, TagBrief } from '@/types/api';

interface SemNoteResult {
  id: string;
  title: string | null;
  updated_at: string;
  tags: TagBrief[];
  chunks: Array<{ idx: number; total: number; content: string }>;
  maxScore: number | null;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 86_400_000) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diff < 604_800_000) return d.toLocaleDateString([], { weekday: 'short' });
  return d.toLocaleDateString([], { day: 'numeric', month: 'short' });
}

const RECENT_KEY = 'nocturn-searches';
const MAX_RECENT = 10;

function useRecentSearches() {
  const [recent, setRecent] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]') as string[]; }
    catch { return []; }
  });

  function add(query: string) {
    const next = [query, ...recent.filter((q) => q !== query)].slice(0, MAX_RECENT);
    setRecent(next);
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  }

  function clear() {
    setRecent([]);
    localStorage.removeItem(RECENT_KEY);
  }

  return { recent, add, clear };
}

export default function SearchPanel() {
  const s = t();
  const { openTab, searchQuery, searchSubmitted, setSearchQuery, setSearchSubmitted } = useUIStore();
  const { recent, add: addRecent, clear: clearRecent } = useRecentSearches();

  const kwQuery = useQuery({
    queryKey: ['search-kw', searchSubmitted],
    queryFn: () => notesApi.search(searchSubmitted),
    enabled: searchSubmitted.length > 0,
    retry: 1,
  });

  const semQuery = useQuery({
    queryKey: ['search-sem', searchSubmitted],
    queryFn: async () => {
      const res = await ragApi.search({ query: searchSubmitted, limit: 20 });
      if (res.results.length === 0) return [] as SemNoteResult[];

      const byNote = new Map<string, SearchResult[]>();
      for (const r of res.results) {
        const arr = byNote.get(r.note_id) ?? [];
        arr.push(r);
        byNote.set(r.note_id, arr);
      }

      const ids = [...byNote.keys()];
      const batch = await notesApi.batch({ note_ids: ids });
      const noteMap = new Map(batch.items.map((n) => [n.id, n]));

      return ids
        .map((id): SemNoteResult | null => {
          const note = noteMap.get(id);
          if (!note) return null;
          const sorted = (byNote.get(id) ?? []).sort((a, b) => a.chunk_index - b.chunk_index);
          const maxScore = sorted.reduce<number | null>(
            (mx, c) => (c.score !== null ? (mx === null ? c.score : Math.max(mx, c.score)) : mx),
            null,
          );
          return {
            id: note.id,
            title: note.title,
            updated_at: note.updated_at,
            tags: note.tags,
            chunks: sorted.map((c, i) => ({ idx: i + 1, total: sorted.length, content: c.content })),
            maxScore,
          };
        })
        .filter((x): x is SemNoteResult => x !== null)
        .sort((a, b) => (b.maxScore ?? 0) - (a.maxScore ?? 0));
    },
    enabled: searchSubmitted.length > 0,
    retry: 1,
  });

  const kwResults: NoteListItem[] = kwQuery.data?.items ?? [];
  const semResults: SemNoteResult[] = semQuery.data ?? [];

  function submit(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    setSearchQuery(trimmed);
    setSearchSubmitted(trimmed);
    addRecent(trimmed);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    submit(searchQuery);
  }

  function handleClear() {
    setSearchQuery('');
    setSearchSubmitted('');
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* Header */}
      <div
        className="flex-shrink-0 flex items-center border-b border-border"
        style={{ height: '40px', padding: '0 16px' }}
      >
        <span className="text-[11px] font-semibold uppercase tracking-widest text-fg-disabled select-none">
          {s.notes.search}
        </span>
      </div>

      {/* Search input */}
      <div className="flex-shrink-0 border-b border-border" style={{ padding: '12px 16px 14px' }}>
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <div className="relative flex-1">
            <svg
              width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              className="absolute pointer-events-none text-fg-disabled"
              style={{ left: '10px', top: '50%', transform: 'translateY(-50%)' }}
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              className="w-full bg-bg-input border border-border rounded text-[13px] text-fg outline-none placeholder:text-fg-muted focus:border-border-focus"
              style={{ padding: '7px 30px 7px 30px' }}
              placeholder={s.notes.searchPlaceholder}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                type="button"
                className="absolute text-fg-disabled hover:text-fg transition-colors"
                style={{ right: '9px', top: '50%', transform: 'translateY(-50%)' }}
                onClick={handleClear}
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            )}
          </div>
          <button
            type="submit"
            className="flex-shrink-0 rounded text-[12px] font-medium transition-opacity disabled:opacity-40"
            style={{ padding: '7px 14px', background: 'var(--color-accent)', color: '#fff' }}
            disabled={!searchQuery.trim() || kwQuery.isFetching || semQuery.isFetching}
          >
            {s.notes.search}
          </button>
        </form>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto">
        {!searchSubmitted ? (
          /* Idle state */
          recent.length > 0 ? (
            <div>
              <div
                className="flex items-center justify-between"
                style={{ padding: '10px 16px 6px' }}
              >
                <span className="text-[11px] font-semibold uppercase tracking-wider text-fg-disabled select-none">
                  {s.notes.recentSearches}
                </span>
                <button
                  className="text-[11px] text-fg-disabled hover:text-fg-muted transition-colors"
                  onClick={clearRecent}
                >
                  {s.common.cancel}
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5" style={{ padding: '4px 16px 14px' }}>
                {recent.map((q) => (
                  <button
                    key={q}
                    className="text-[12px] text-fg-muted hover:text-fg border border-border hover:border-border-focus rounded transition-colors truncate"
                    style={{ padding: '4px 10px', maxWidth: '180px' }}
                    onClick={() => submit(q)}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-40 gap-2.5 text-fg-disabled">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span className="text-[12px]">{s.notes.searchPlaceholder}</span>
            </div>
          )
        ) : (
          <>
            {/* ── Keyword section ── */}
            <div className="border-b border-border">
              <SectionHeader
                label={s.notes.keywordSection}
                count={kwResults.length}
                loading={kwQuery.isFetching}
                error={kwQuery.isError}
                onRetry={() => void kwQuery.refetch()}
                retryLabel={s.common.retry}
                errorLabel={s.common.error}
              />
              {kwQuery.isFetching ? (
                <SearchSkeleton />
              ) : kwQuery.isError ? null : kwResults.length === 0 ? (
                <SectionEmpty label={s.notes.noResults} />
              ) : (
                kwResults.map((note) => (
                  <KeywordRow
                    key={note.id}
                    note={note}
                    onClick={() => openTab({ type: 'note', id: note.id })}
                  />
                ))
              )}
            </div>

            {/* ── Semantic section ── */}
            <div>
              <SectionHeader
                label={s.notes.semanticSearch}
                count={semResults.length}
                loading={semQuery.isFetching}
                error={semQuery.isError}
                onRetry={() => void semQuery.refetch()}
                retryLabel={s.common.retry}
                errorLabel={s.common.error}
              />
              {semQuery.isFetching ? (
                <SearchSkeleton />
              ) : semQuery.isError ? null : semResults.length === 0 ? (
                <SectionEmpty label={s.notes.noResults} />
              ) : (
                <div style={{ padding: '10px 14px 14px' }}>
                  {semResults.map((result) => (
                    <SemanticCard
                      key={result.id}
                      result={result}
                      onClick={() => openTab({ type: 'note', id: result.id })}
                    />
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Section header ─────────────────────────────────────────────────────────────

function SectionHeader({
  label, count, loading, error, onRetry, retryLabel, errorLabel,
}: {
  label: string;
  count: number;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  retryLabel: string;
  errorLabel: string;
}) {
  return (
    <div className="flex items-center justify-between" style={{ padding: '10px 16px 8px' }}>
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted select-none">
          {label}
        </span>
        {!loading && !error && (
          <span className="text-[11px] text-fg-disabled">· {count}</span>
        )}
        {loading && (
          <span className="text-[11px] text-fg-disabled">· ···</span>
        )}
      </div>
      {error && (
        <div className="flex items-center gap-2">
          <span className="text-[11px]" style={{ color: 'var(--color-danger)' }}>{errorLabel}</span>
          <button
            className="text-[11px] text-fg-muted hover:text-fg border border-border rounded transition-colors"
            style={{ padding: '2px 8px' }}
            onClick={onRetry}
          >
            ↺ {retryLabel}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Section empty ──────────────────────────────────────────────────────────────

function SectionEmpty({ label }: { label: string }) {
  return (
    <div className="text-fg-muted text-[12px]" style={{ padding: '4px 16px 12px' }}>
      {label}
    </div>
  );
}

// ── Skeleton ───────────────────────────────────────────────────────────────────

function SearchSkeleton() {
  return (
    <div style={{ padding: '4px 14px 12px' }}>
      {[1, 0.7, 0.45].map((op, i) => (
        <div
          key={i}
          className="rounded border border-border/50"
          style={{
            height: '64px',
            marginBottom: '8px',
            background: 'var(--color-bg-hover)',
            opacity: op,
            animation: 'pulse 1.5s infinite',
          }}
        />
      ))}
    </div>
  );
}

// ── Keyword row ────────────────────────────────────────────────────────────────

function KeywordRow({ note, onClick }: { note: NoteListItem; onClick: () => void }) {
  const s = t();
  return (
    <div
      className="flex items-center gap-3 cursor-pointer border-b border-border/40 hover:bg-bg-hover"
      style={{ padding: '10px 16px 10px 14px' }}
      onClick={onClick}
    >
      <svg
        width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
        className="flex-shrink-0 text-fg-disabled"
        style={{ marginTop: '1px' }}
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
      </svg>

      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-medium truncate leading-snug text-fg">
          {note.title ?? (
            <span className="text-fg-muted italic font-normal">{s.notes.untitled}</span>
          )}
        </div>

        {note.tags.length > 0 && (
          <div className="flex flex-wrap gap-1" style={{ marginTop: '6px' }}>
            {note.tags.map((tag) => (
              <span
                key={tag.id}
                className="text-[11px] leading-none rounded"
                style={{ padding: '2px 7px', background: 'var(--color-bg-input)', color: 'var(--color-fg-muted)' }}
              >
                #{tag.name}
              </span>
            ))}
          </div>
        )}

        <div
          className="text-[11px] leading-none text-fg-disabled"
          style={{ marginTop: note.tags.length > 0 ? '5px' : '4px' }}
        >
          {formatDate(note.updated_at)}
        </div>
      </div>
    </div>
  );
}

// ── Semantic card ──────────────────────────────────────────────────────────────

function SemanticCard({ result, onClick }: { result: SemNoteResult; onClick: () => void }) {
  const s = t();
  const scoreStr = result.maxScore !== null ? `${Math.round(result.maxScore * 100)}%` : null;

  return (
    <div
      className="cursor-pointer rounded border border-border hover:border-accent transition-colors"
      style={{ padding: '10px 12px', marginBottom: '8px', background: 'var(--color-bg-sidebar)' }}
      onClick={onClick}
    >
      {/* Title + score */}
      <div className="flex items-center justify-between gap-2" style={{ marginBottom: '6px' }}>
        <div className="text-[13px] font-semibold truncate text-fg">
          {result.title ?? (
            <span className="text-fg-muted italic font-normal">{s.notes.untitled}</span>
          )}
        </div>
        {scoreStr && (
          <span
            className="flex-shrink-0 text-[11px] font-bold rounded"
            style={{ padding: '2px 7px', background: 'var(--color-bg-selected)', color: 'var(--color-accent)' }}
          >
            {scoreStr}
          </span>
        )}
      </div>

      {/* Chunks */}
      {result.chunks.map((chunk, i) => (
        <div key={i}>
          {i > 0 && (
            <div className="border-t border-border/60" style={{ margin: '7px 0' }} />
          )}
          {result.chunks.length > 1 && (
            <div className="text-[10px] text-fg-disabled" style={{ marginBottom: '3px' }}>
              {chunk.idx} / {chunk.total}
            </div>
          )}
          <div className="text-[12px] leading-relaxed text-fg-muted line-clamp-3">
            {chunk.content}
          </div>
        </div>
      ))}

      {/* Tags + date */}
      <div className="flex flex-wrap items-center gap-1.5" style={{ marginTop: '8px' }}>
        {result.tags.map((tag) => (
          <span
            key={tag.id}
            className="text-[11px] leading-none rounded"
            style={{ padding: '2px 7px', background: 'var(--color-bg-input)', color: 'var(--color-fg-muted)' }}
          >
            #{tag.name}
          </span>
        ))}
        <span className="text-[11px] text-fg-disabled" style={{ marginLeft: 'auto' }}>
          {formatDate(result.updated_at)}
        </span>
      </div>
    </div>
  );
}
