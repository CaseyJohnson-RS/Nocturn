import { useCallback, useEffect, useState } from "react";
import { RotateCcw, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/stores/i18n";
import { useNotes } from "@/stores/notes";
import { useTabs, type ListTab as ListTabType } from "@/stores/tabs";
import { useToast } from "@/stores/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import type { NoteListItem } from "@/api/types";

// ---------------------------------------------------------------------------
// Note row
// ---------------------------------------------------------------------------

function NoteRow({
  note,
  isTrash,
  onOpen,
  onRestore,
  onDeletePermanent,
}: {
  note: NoteListItem;
  isTrash: boolean;
  onOpen: () => void;
  onRestore: () => void;
  onDeletePermanent: () => void;
}) {
  const { t } = useI18n();
  const title = note.title || t("common.untitled");
  const date = new Date(note.updated_at).toLocaleDateString();

  return (
    <div
      draggable={!isTrash}
      onClick={isTrash ? undefined : onOpen}
      onDragStart={(e) => {
        if (!isTrash) {
          e.dataTransfer.setData("application/nocturn-note-id", note.id);
          e.dataTransfer.effectAllowed = "copy";
        }
      }}
      className={cn(
        "group flex items-center gap-3 rounded-md px-3 py-2.5 transition-colors",
        !isTrash && "cursor-pointer hover:bg-accent/50",
        isTrash && "opacity-70",
      )}
    >
      <div className="flex-1 min-w-0">
        <div className={cn("text-sm font-medium truncate", isTrash && "line-through")}>
          {title}
        </div>
        <div className="text-[11px] text-muted-foreground mt-0.5">{date}</div>
      </div>

      {isTrash && (
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={(e) => { e.stopPropagation(); onRestore(); }}
            className="rounded p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
            title={t("trash.restoreNote")}
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDeletePermanent(); }}
            className="rounded p-1.5 text-muted-foreground hover:bg-destructive/20 hover:text-destructive transition-colors"
            title={t("trash.deletePermanent")}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ListViewTab
// ---------------------------------------------------------------------------

export function ListViewTab({ filter }: { filter: ListTabType["filter"] }) {
  const { t } = useI18n();
  const { fetchNotes, restoreNote, deleteNote } = useNotes();
  const { openNote } = useTabs();
  const { addToast } = useToast();

  const [notes, setNotes] = useState<NoteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const isTrash = filter === "trash";
  const tagFilter = typeof filter === "object" ? filter : null;

  // Load notes
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const items = await fetchNotes({
        deleted: isTrash || undefined,
        tag_ids: tagFilter ? [tagFilter.tagId] : undefined,
      });
      setNotes(items);
    } catch (err: unknown) {
      addToast("error", (err as Error).message || t("toast.networkError"));
    } finally {
      setLoading(false);
    }
  }, [fetchNotes, isTrash, tagFilter, addToast, t]);

  useEffect(() => { load(); }, [load]);

  // Filter locally by search
  const filtered = search
    ? notes.filter((n) =>
        (n.title || "").toLowerCase().includes(search.toLowerCase()),
      )
    : notes;

  const handleRestore = useCallback(
    async (id: string) => {
      try {
        await restoreNote(id);
        setNotes((prev) => prev.filter((n) => n.id !== id));
      } catch (err: unknown) {
        addToast("error", (err as Error).message || t("toast.networkError"));
      }
    },
    [restoreNote, addToast, t],
  );

  const handleDeletePermanent = useCallback(
    async (id: string) => {
      try {
        await deleteNote(id, true);
        setNotes((prev) => prev.filter((n) => n.id !== id));
      } catch (err: unknown) {
        addToast("error", (err as Error).message || t("toast.networkError"));
      }
    },
    [deleteNote, addToast, t],
  );

  const handleOpen = useCallback(
    (note: NoteListItem) => {
      openNote(note.id, note.title || undefined);
    },
    [openNote],
  );

  return (
    <div className="flex flex-1 flex-col min-h-0">
      {/* Search */}
      <div className="px-4 pt-4 pb-2">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("common.search") + "..."}
          className="h-8 text-sm"
        />
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
            {t("common.loading")}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <p className="text-sm">
              {isTrash ? t("trash.empty") : t("notes.empty")}
            </p>
            {!isTrash && (
              <p className="text-xs mt-1">{t("notes.emptyHint")}</p>
            )}
          </div>
        ) : (
          <div className="space-y-0.5">
            {filtered.map((note) => (
              <NoteRow
                key={note.id}
                note={note}
                isTrash={isTrash}
                onOpen={() => handleOpen(note)}
                onRestore={() => handleRestore(note.id)}
                onDeletePermanent={() => setConfirmDelete(note.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Confirm permanent delete */}
      <ConfirmDialog
        open={confirmDelete !== null}
        onOpenChange={(open) => !open && setConfirmDelete(null)}
        title={t("notes.deleteConfirm")}
        description={t("notes.deleteConfirmText")}
        confirmLabel={t("notes.deletePermanent")}
        cancelLabel={t("common.cancel")}
        variant="destructive"
        onConfirm={() => {
          if (confirmDelete) handleDeletePermanent(confirmDelete);
        }}
      />
    </div>
  );
}
