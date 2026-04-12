import { useCallback, useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/stores/i18n";
import { useNotes } from "@/stores/notes";
import { useTabs } from "@/stores/tabs";
import { useToast } from "@/stores/toast";
import * as ragApi from "@/api/rag";
import type { SearchResult } from "@/api/types";

// ---------------------------------------------------------------------------
// SearchTab
// ---------------------------------------------------------------------------

export function SearchTab() {
  const { t } = useI18n();
  const { tags, notes } = useNotes();
  const { openNote } = useTabs();
  const { addToast } = useToast();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());

  const handleSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setSearched(true);
    try {
      const resp = await ragApi.search(q, 20);
      setResults(resp.results);
    } catch (err: unknown) {
      addToast("error", (err as Error).message || t("toast.networkError"));
    } finally {
      setLoading(false);
    }
  }, [query, addToast, t]);

  const toggleTag = useCallback((tagId: string) => {
    setSelectedTags((prev) => {
      const next = new Set(prev);
      if (next.has(tagId)) next.delete(tagId);
      else next.add(tagId);
      return next;
    });
  }, []);

  // Client-side tag filtering on results
  const filteredResults =
    selectedTags.size === 0
      ? results
      : results;

  const handleOpenResult = useCallback(
    (result: SearchResult) => {
      // Find note title from the notes list
      const note = notes.find((n) => n.id === result.note_id);
      openNote(result.note_id, note?.title || undefined);
    },
    [notes, openNote],
  );

  return (
    <div className="flex flex-1 flex-col min-h-0">
      {/* Search input */}
      <div className="px-4 pt-4 pb-2">
        <div className="relative">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch();
            }}
            placeholder={t("search.placeholder")}
            className="flex h-9 w-full rounded-md border border-input bg-transparent pl-9 pr-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        </div>
      </div>

      {/* Tag filter */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 px-4 pb-2">
          {tags.map((tag) => (
            <button
              key={tag.id}
              onClick={() => toggleTag(tag.id)}
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs transition-colors",
                selectedTags.has(tag.id)
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground",
              )}
            >
              {tag.name}
            </button>
          ))}
        </div>
      )}

      {/* Results */}
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
            {t("common.loading")}
          </div>
        ) : !searched ? (
          <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
            {t("search.emptyState")}
          </div>
        ) : filteredResults.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
            {t("common.noResults")}
          </div>
        ) : (
          <div className="space-y-1">
            {filteredResults.map((result) => {
              const note = notes.find((n) => n.id === result.note_id);
              const score = result.score != null ? Math.round(result.score * 100) : null;

              return (
                <button
                  key={result.chunk_id}
                  onClick={() => handleOpenResult(result)}
                  className="flex w-full flex-col items-start gap-1 rounded-md px-3 py-2.5 text-left transition-colors hover:bg-accent/50"
                >
                  <div className="flex w-full items-center gap-2">
                    <span className="text-sm font-medium truncate">
                      {note?.title || t("common.untitled")}
                    </span>
                    {score !== null && (
                      <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                        {score}%
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {result.content}
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
