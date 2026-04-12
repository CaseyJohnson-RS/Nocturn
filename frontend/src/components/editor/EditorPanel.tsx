import { FileText, Plus } from "lucide-react";
import { useI18n } from "@/stores/i18n";
import { useNotes } from "@/stores/notes";
import { useTabs } from "@/stores/tabs";
import { useToast } from "@/stores/toast";
import { TabBar } from "@/components/layout/TabBar";
import { NoteTab } from "./NoteTab";
import { ListViewTab } from "./ListViewTab";
import { SearchTab } from "./SearchTab";

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState() {
  const { t } = useI18n();
  const { createNote } = useNotes();
  const { openNote } = useTabs();
  const { addToast } = useToast();

  const handleCreate = async () => {
    try {
      const note = await createNote();
      openNote(note.id, note.title || undefined);
    } catch (err) {
      addToast("error", (err as Error).message || t("toast.networkError"));
    }
  };

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 text-muted-foreground">
      <FileText className="h-12 w-12 opacity-30" />
      <div className="text-center">
        <p className="text-sm font-medium">{t("editor.welcome")}</p>
        <p className="text-xs mt-1">{t("editor.welcomeHint")}</p>
      </div>
      <button
        onClick={handleCreate}
        className="flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        <Plus className="h-4 w-4" />
        {t("notes.createNote")}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab content router
// ---------------------------------------------------------------------------

function TabContent() {
  const { tabs, activeTabId } = useTabs();
  const activeTab = tabs.find((t) => t.id === activeTabId);

  if (!activeTab) return <EmptyState />;

  switch (activeTab.type) {
    case "note":
      return <NoteTab key={activeTab.noteId} noteId={activeTab.noteId} />;
    case "list":
      return <ListViewTab key={activeTab.id} filter={activeTab.filter} />;
    case "search":
      return <SearchTab />;
    default:
      return <EmptyState />;
  }
}

// ---------------------------------------------------------------------------
// EditorPanel
// ---------------------------------------------------------------------------

export function EditorPanel() {
  return (
    <div className="flex flex-1 flex-col min-w-0 min-h-0">
      <TabBar />
      <TabContent />
    </div>
  );
}
