import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { X, Plus, Check } from "lucide-react";
import { useI18n } from "@/stores/i18n";
import { useNotes } from "@/stores/notes";
import { useTabs } from "@/stores/tabs";
import { useChat } from "@/stores/chat";
import { useToast } from "@/stores/toast";
import { MarkdownEditor } from "./MarkdownEditor";
import { DiffView } from "./DiffView";
import { Badge } from "@/components/ui/badge";
import * as notesApi from "@/api/notes";
import type { Note, TagBrief, Tag, Proposal } from "@/api/types";

// ---------------------------------------------------------------------------
// Tag bar
// ---------------------------------------------------------------------------

function TagBar({
  tags,
  allTags,
  onRemove,
  onAdd,
  onCreate,
}: {
  tags: TagBrief[];
  allTags: Tag[];
  onRemove: (tagId: string) => void;
  onAdd: (tagId: string) => void;
  onCreate: (name: string) => void;
}) {
  const { t } = useI18n();
  const [showPicker, setShowPicker] = useState(false);
  const [filter, setFilter] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const tagIds = new Set(tags.map((t) => t.id));
  const available = allTags.filter(
    (t) =>
      !tagIds.has(t.id) &&
      t.name.toLowerCase().includes(filter.toLowerCase()),
  );
  const canCreate =
    filter.trim().length > 0 &&
    !allTags.some((t) => t.name.toLowerCase() === filter.trim().toLowerCase());

  useEffect(() => {
    if (showPicker) inputRef.current?.focus();
  }, [showPicker]);

  return (
    <div className="flex flex-wrap items-center gap-1.5 px-6 py-2 border-b border-border">
      {tags.map((tag) => (
        <Badge
          key={tag.id}
          variant="secondary"
          className="gap-1 pr-1 text-xs font-normal"
        >
          {tag.name}
          <button
            onClick={() => onRemove(tag.id)}
            className="rounded-full p-0.5 hover:bg-accent"
          >
            <X className="h-2.5 w-2.5" />
          </button>
        </Badge>
      ))}

      {showPicker ? (
        <div className="relative">
          <input
            ref={inputRef}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setShowPicker(false);
                setFilter("");
              }
              if (e.key === "Enter" && canCreate) {
                onCreate(filter.trim());
                setFilter("");
                setShowPicker(false);
              }
            }}
            onBlur={() => {
              setTimeout(() => {
                setShowPicker(false);
                setFilter("");
              }, 200);
            }}
            placeholder={t("editor.addTag")}
            className="h-6 w-28 rounded border border-input bg-transparent px-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
          {(available.length > 0 || canCreate) && (
            <div className="absolute left-0 top-7 z-50 max-h-40 w-40 overflow-y-auto rounded-md border bg-popover p-1 shadow-md">
              {available.map((tag) => (
                <button
                  key={tag.id}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onAdd(tag.id);
                    setFilter("");
                    setShowPicker(false);
                  }}
                  className="flex w-full items-center rounded-sm px-2 py-1 text-xs hover:bg-accent"
                >
                  {tag.name}
                </button>
              ))}
              {canCreate && (
                <button
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onCreate(filter.trim());
                    setFilter("");
                    setShowPicker(false);
                  }}
                  className="flex w-full items-center gap-1 rounded-sm px-2 py-1 text-xs text-primary hover:bg-accent"
                >
                  <Plus className="h-3 w-3" />
                  {t("editor.createTag")} "{filter.trim()}"
                </button>
              )}
            </div>
          )}
        </div>
      ) : (
        <button
          onClick={() => setShowPicker(true)}
          className="flex h-5 items-center gap-0.5 rounded px-1 text-[11px] text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <Plus className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hook: find first pending edit_note proposal targeting this noteId
// ---------------------------------------------------------------------------

function usePendingEditProposal(noteId: string): {
  proposal: Proposal | null;
  messageId: string | null;
} {
  const { messages } = useChat();

  return useMemo(() => {
    for (const msg of messages) {
      if (!msg.actions) continue;
      for (const action of msg.actions) {
        if (
          action.type === "proposal" &&
          action.proposal_type === "edit_note" &&
          action.note_id === noteId &&
          action.status === "pending"
        ) {
          return { proposal: action, messageId: msg.id };
        }
      }
    }
    return { proposal: null, messageId: null };
  }, [messages, noteId]);
}

// ---------------------------------------------------------------------------
// NoteTab
// ---------------------------------------------------------------------------

export function NoteTab({ noteId }: { noteId: string }) {
  const { t } = useI18n();
  const {
    getNote,
    saveNote,
    tags: allTags,
    updateNoteTags,
    createTag,
    fetchNotes,
    isSaving,
  } = useNotes();
  const { updateTabTitle, setTabDirty } = useTabs();
  const { applyAction, dismissAction } = useChat();
  const { addToast } = useToast();

  const [note, setNote] = useState<Note | null>(null);
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState("");
  const versionRef = useRef(0);
  const tabId = `note-${noteId}`;

  // Active proposal for this note
  const { proposal, messageId } = usePendingEditProposal(noteId);

  // Load note
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getNote(noteId)
      .then((n) => {
        if (cancelled) return;
        setNote(n);
        setTitle(n.title || "");
        versionRef.current = n.version;
        updateTabTitle(tabId, n.title || t("common.untitled"));
      })
      .catch((err) => {
        if (cancelled) return;
        addToast("error", err.message || t("toast.networkError"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [noteId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Save handlers
  const handleTitleChange = useCallback(
    (newTitle: string) => {
      setTitle(newTitle);
      setTabDirty(tabId, true);
      updateTabTitle(tabId, newTitle || t("common.untitled"));
      saveNote(noteId, { title: newTitle }, versionRef.current, (updated) => {
        versionRef.current = updated.version;
        setTabDirty(tabId, false);
      });
    },
    [noteId, tabId, saveNote, setTabDirty, updateTabTitle, t],
  );

  const handleContentChange = useCallback(
    (content: string) => {
      setTabDirty(tabId, true);
      saveNote(noteId, { content }, versionRef.current, (updated) => {
        versionRef.current = updated.version;
        setTabDirty(tabId, false);
      });
    },
    [noteId, tabId, saveNote, setTabDirty],
  );

  // --- Proposal handlers (cross-panel sync) ---

  const handleDiffApply = useCallback(
    async (finalContent: string) => {
      if (!proposal || !messageId) return;
      try {
        // Apply the content change to the note
        const updated = await notesApi.updateNote(noteId, {
          content: finalContent,
          version: versionRef.current,
        });
        versionRef.current = updated.version;
        setNote(updated);
        // Mark proposal as applied in the chat store (syncs to Chat panel)
        await applyAction(messageId, proposal.id);
        await fetchNotes();
      } catch (err) {
        addToast("error", (err as Error).message || t("toast.serverError"));
      }
    },
    [proposal, messageId, noteId, applyAction, fetchNotes, addToast, t],
  );

  const handleDiffDismiss = useCallback(async () => {
    if (!proposal || !messageId) return;
    try {
      await dismissAction(messageId, proposal.id);
    } catch (err) {
      addToast("error", (err as Error).message || t("toast.serverError"));
    }
  }, [proposal, messageId, dismissAction, addToast, t]);

  // --- Tag operations ---

  const handleRemoveTag = useCallback(
    async (tagId: string) => {
      if (!note) return;
      const newTagIds = note.tags
        .filter((t) => t.id !== tagId)
        .map((t) => t.id);
      const updated = await updateNoteTags(noteId, newTagIds);
      setNote(updated);
    },
    [note, noteId, updateNoteTags],
  );

  const handleAddTag = useCallback(
    async (tagId: string) => {
      if (!note) return;
      const newTagIds = [...note.tags.map((t) => t.id), tagId];
      const updated = await updateNoteTags(noteId, newTagIds);
      setNote(updated);
    },
    [note, noteId, updateNoteTags],
  );

  const handleCreateTag = useCallback(
    async (name: string) => {
      if (!note) return;
      const tag = await createTag(name);
      const newTagIds = [...note.tags.map((t) => t.id), tag.id];
      const updated = await updateNoteTags(noteId, newTagIds);
      setNote(updated);
    },
    [note, noteId, createTag, updateNoteTags],
  );

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p className="text-sm">{t("common.loading")}</p>
      </div>
    );
  }

  if (!note) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p className="text-sm">Note not found</p>
      </div>
    );
  }

  // If there's an active edit_note proposal, show diff view instead of editor
  const showDiff =
    proposal &&
    proposal.data?.content != null;

  return (
    <div className="flex flex-1 flex-col min-h-0">
      {/* Title */}
      <div className="px-6 pt-4 pb-1">
        <input
          value={title}
          onChange={(e) => handleTitleChange(e.target.value)}
          placeholder={t("common.untitled")}
          disabled={!!showDiff}
          className="w-full bg-transparent text-2xl font-bold outline-none placeholder:text-muted-foreground/50 disabled:opacity-60"
        />
        {isSaving(noteId) && !showDiff && (
          <div className="flex items-center gap-1 mt-1">
            <Check className="h-3 w-3 text-muted-foreground animate-pulse" />
            <span className="text-[11px] text-muted-foreground">
              {t("common.save")}...
            </span>
          </div>
        )}
      </div>

      {/* Tags */}
      <TagBar
        tags={note.tags}
        allTags={allTags}
        onRemove={handleRemoveTag}
        onAdd={handleAddTag}
        onCreate={handleCreateTag}
      />

      {/* Editor or Diff View */}
      {showDiff ? (
        <DiffView
          originalContent={note.content || ""}
          proposedContent={proposal.data!.content as string}
          summary={proposal.summary}
          onApply={handleDiffApply}
          onDismiss={handleDiffDismiss}
        />
      ) : (
        <div className="flex-1 min-h-0 overflow-hidden">
          <MarkdownEditor
            initialContent={note.content || ""}
            onChange={handleContentChange}
          />
        </div>
      )}
    </div>
  );
}
