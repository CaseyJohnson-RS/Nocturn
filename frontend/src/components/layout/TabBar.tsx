import { useRef, useCallback, useState } from "react";
import { X, FileText, List, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTabs, type Tab } from "@/stores/tabs";
import { useI18n } from "@/stores/i18n";

// ---------------------------------------------------------------------------
// Single tab (with drag & drop)
// ---------------------------------------------------------------------------

function TabItem({
  tab,
  index,
  active,
  onActivate,
  onClose,
  onDragStart,
  onDragOver,
  onDrop,
  dropTarget,
}: {
  tab: Tab;
  index: number;
  active: boolean;
  onActivate: () => void;
  onClose: (e: React.MouseEvent) => void;
  onDragStart: (index: number) => void;
  onDragOver: (e: React.DragEvent, index: number) => void;
  onDrop: (index: number) => void;
  dropTarget: boolean;
}) {
  const { t } = useI18n();
  const isDirty = tab.type === "note" && tab.dirty;

  const icon =
    tab.type === "note" ? (
      <FileText className="h-3.5 w-3.5 shrink-0" />
    ) : tab.type === "list" ? (
      <List className="h-3.5 w-3.5 shrink-0" />
    ) : (
      <Search className="h-3.5 w-3.5 shrink-0" />
    );

  const title = tab.title || t("common.untitled");

  return (
    <div
      role="tab"
      aria-selected={active}
      draggable
      onClick={onActivate}
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", tab.id);
        onDragStart(index);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        onDragOver(e, index);
      }}
      onDrop={(e) => {
        e.preventDefault();
        onDrop(index);
      }}
      className={cn(
        "group relative flex h-full min-w-0 max-w-48 shrink-0 cursor-pointer select-none items-center gap-1.5 border-r border-border px-3 text-xs transition-colors",
        active
          ? "bg-background text-foreground"
          : "bg-card/50 text-muted-foreground hover:bg-card hover:text-foreground",
        dropTarget && "border-l-2 border-l-primary",
      )}
    >
      {icon}
      <span className="truncate">{title}</span>
      {isDirty && (
        <span className="ml-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
      )}
      <button
        onClick={onClose}
        className={cn(
          "ml-auto shrink-0 rounded p-0.5 transition-colors hover:bg-accent",
          !active && "opacity-0 group-hover:opacity-100",
        )}
        aria-label="Close tab"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TabBar
// ---------------------------------------------------------------------------

export function TabBar() {
  const { tabs, activeTabId, setActiveTab, closeTab, reorderTabs } = useTabs();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [dropIdx, setDropIdx] = useState<number | null>(null);

  const handleClose = useCallback(
    (e: React.MouseEvent, tabId: string) => {
      e.stopPropagation();
      closeTab(tabId);
    },
    [closeTab],
  );

  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft += e.deltaY;
    }
  }, []);

  const handleDragStart = useCallback((index: number) => {
    setDragFrom(index);
  }, []);

  const handleDragOver = useCallback(
    (_e: React.DragEvent, index: number) => {
      if (dragFrom !== null && dragFrom !== index) {
        setDropIdx(index);
      }
    },
    [dragFrom],
  );

  const handleDrop = useCallback(
    (toIndex: number) => {
      if (dragFrom !== null && dragFrom !== toIndex) {
        reorderTabs(dragFrom, toIndex);
      }
      setDragFrom(null);
      setDropIdx(null);
    },
    [dragFrom, reorderTabs],
  );

  const handleDragEnd = useCallback(() => {
    setDragFrom(null);
    setDropIdx(null);
  }, []);

  if (tabs.length === 0) return null;

  return (
    <div
      ref={scrollRef}
      role="tablist"
      className="flex h-9 shrink-0 overflow-x-auto overflow-y-hidden border-b border-border bg-card/30 scrollbar-none"
      onWheel={handleWheel}
      onDragEnd={handleDragEnd}
    >
      {tabs.map((tab, i) => (
        <TabItem
          key={tab.id}
          tab={tab}
          index={i}
          active={tab.id === activeTabId}
          onActivate={() => setActiveTab(tab.id)}
          onClose={(e) => handleClose(e, tab.id)}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          dropTarget={dropIdx === i && dragFrom !== i}
        />
      ))}
    </div>
  );
}
