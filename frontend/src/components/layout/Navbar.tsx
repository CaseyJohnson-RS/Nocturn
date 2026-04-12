import { useCallback, useState } from "react";
import { useToast } from "@/stores/toast";
import {
  Plus,
  FileText,
  Search,
  Trash2,
  Tag,
  MessageSquare,
  Sun,
  Moon,
  LogOut,
  ChevronDown,
  ChevronRight,
  Globe,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/stores/i18n";
import { useTheme } from "@/stores/theme";
import { useAuth } from "@/stores/auth";
import { useNotes } from "@/stores/notes";
import { useChat } from "@/stores/chat";
import { useTabs, type ListTab } from "@/stores/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { NoteListItem, Tag as TagType } from "@/api/types";

// ---------------------------------------------------------------------------
// Nav icon button
// ---------------------------------------------------------------------------

function NavButton({
  icon: Icon,
  label,
  active,
  badge,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  active?: boolean;
  badge?: number;
  onClick: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={onClick}
          className={cn(
            "relative flex h-9 w-9 items-center justify-center rounded-md transition-colors",
            active
              ? "bg-accent text-accent-foreground"
              : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
          )}
        >
          <Icon className="h-[18px] w-[18px]" />
          {badge != null && badge > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
              {badge > 99 ? "99+" : badge}
            </span>
          )}
        </button>
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

// ---------------------------------------------------------------------------
// Recent notes section
// ---------------------------------------------------------------------------

function RecentNotes({ notes }: { notes: NoteListItem[] }) {
  const { t } = useI18n();
  const { openNote } = useTabs();
  const [expanded, setExpanded] = useState(true);

  const recent = notes
    .filter((n) => !n.deleted_at)
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 5);

  if (recent.length === 0) return null;

  return (
    <div className="mt-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-1 px-1 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground hover:text-foreground"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        {t("notes.recent")}
      </button>
      {expanded && (
        <div className="mt-0.5 space-y-px">
          {recent.map((note) => (
            <button
              key={note.id}
              draggable
              onClick={() => openNote(note.id, note.title || undefined)}
              onDragStart={(e) => {
                e.dataTransfer.setData("application/nocturn-note-id", note.id);
                e.dataTransfer.effectAllowed = "copy";
              }}
              className="flex w-full items-center rounded px-1.5 py-1 text-[11px] text-muted-foreground hover:bg-accent/50 hover:text-foreground truncate"
              title={note.title || t("common.untitled")}
            >
              <span className="truncate">
                {note.title || t("common.untitled")}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tags section
// ---------------------------------------------------------------------------

function TagsList({ tags }: { tags: TagType[] }) {
  const { t } = useI18n();
  const { openList } = useTabs();
  const [expanded, setExpanded] = useState(false);

  if (tags.length === 0) return null;

  return (
    <div className="mt-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-1 px-1 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground hover:text-foreground"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        {t("nav.tags")}
      </button>
      {expanded && (
        <div className="mt-0.5 space-y-px">
          {tags.map((tag) => (
            <button
              key={tag.id}
              onClick={() =>
                openList(
                  { tagId: tag.id, tagName: tag.name } as ListTab["filter"],
                  `#${tag.name}`,
                )
              }
              className="flex w-full items-center rounded px-1.5 py-1 text-[11px] text-muted-foreground hover:bg-accent/50 hover:text-foreground truncate"
            >
              <Tag className="mr-1 h-3 w-3 shrink-0" />
              <span className="truncate">{tag.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pending proposals count
// ---------------------------------------------------------------------------

function usePendingProposalCount(): number {
  const { messages } = useChat();
  let count = 0;
  for (const msg of messages) {
    if (!msg.actions) continue;
    for (const a of msg.actions) {
      if (a.status === "pending") count++;
    }
  }
  return count;
}

// ---------------------------------------------------------------------------
// Navbar
// ---------------------------------------------------------------------------

export function Navbar() {
  const { t, locale, setLocale } = useI18n();
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const { notes, tags, createNote } = useNotes();
  const { chatOpen, toggleChat } = useChat();
  const { openNote, openList, openSearch, tabs, activeTabId } = useTabs();
  const { addToast } = useToast();
  const pendingCount = usePendingProposalCount();

  const handleNewNote = useCallback(async () => {
    try {
      const note = await createNote();
      openNote(note.id, note.title || undefined);
    } catch (err) {
      addToast("error", (err as Error).message || t("toast.networkError"));
    }
  }, [createNote, openNote, addToast, t]);

  // Check active tab type for highlighting
  const activeTab = tabs.find((t) => t.id === activeTabId);
  const isAllActive = activeTab?.type === "list" && activeTab.filter === "all";
  const isTrashActive = activeTab?.type === "list" && activeTab.filter === "trash";
  const isSearchActive = activeTab?.type === "search";

  return (
    <TooltipProvider delayDuration={300}>
      <nav className="shrink-0 w-14 border-r border-border bg-sidebar flex flex-col items-center py-3 gap-1 overflow-hidden">
        {/* Brand */}
        <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/20 text-sm font-bold text-primary">
          N
        </div>

        {/* New note */}
        <NavButton
          icon={Plus}
          label={t("nav.newNote")}
          onClick={handleNewNote}
        />

        <div className="my-1 h-px w-8 bg-border" />

        {/* All notes */}
        <NavButton
          icon={FileText}
          label={t("nav.allNotes")}
          active={isAllActive}
          onClick={() => openList("all", t("tabs.allNotes"))}
        />

        {/* Search */}
        <NavButton
          icon={Search}
          label={t("nav.search")}
          active={isSearchActive}
          onClick={openSearch}
        />

        {/* Trash */}
        <NavButton
          icon={Trash2}
          label={t("nav.trash")}
          active={isTrashActive}
          onClick={() => openList("trash", t("tabs.trash"))}
        />

        {/* Chat toggle */}
        <NavButton
          icon={MessageSquare}
          label={t("nav.chat")}
          active={chatOpen}
          badge={pendingCount}
          onClick={toggleChat}
        />

        {/* Expandable sections */}
        <div className="mt-1 w-full flex-1 overflow-y-auto overflow-x-hidden px-1.5 scrollbar-thin">
          <RecentNotes notes={notes} />
          <TagsList tags={tags} />
        </div>

        {/* Bottom section */}
        <div className="mt-auto flex flex-col items-center gap-1 pt-2">
          {/* Theme toggle */}
          <NavButton
            icon={theme === "dark" ? Sun : Moon}
            label={t("nav.theme")}
            onClick={toggleTheme}
          />

          {/* User menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/20 text-xs font-medium text-primary">
                  {user?.nickname?.charAt(0).toUpperCase() || "?"}
                </div>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="right" align="end" className="w-48">
              <div className="px-2 py-1.5 text-sm font-medium">
                {user?.nickname || user?.email}
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => setLocale(locale === "ru" ? "en" : "ru")}>
                <Globe className="mr-2 h-4 w-4" />
                {locale === "ru" ? "English" : "Русский"}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => logout()}>
                <LogOut className="mr-2 h-4 w-4" />
                {t("auth.logout")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </nav>
    </TooltipProvider>
  );
}
