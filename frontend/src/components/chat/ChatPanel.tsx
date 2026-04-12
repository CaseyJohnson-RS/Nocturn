import { useEffect, useRef, useState, useCallback } from "react";
import {
  X,
  Plus,
  Send,
  Square,
  Trash2,
  MoreHorizontal,
  Paperclip,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { useChat } from "@/stores/chat";
import { useNotes } from "@/stores/notes";
import { useI18n } from "@/stores/i18n";
import { ChatMessageBubble } from "./ChatMessage";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Note picker popover
// ---------------------------------------------------------------------------

function NotePicker({
  open,
  onClose,
  onPick,
}: {
  open: boolean;
  onClose: () => void;
  onPick: (noteId: string) => void;
}) {
  const { t } = useI18n();
  const { notes } = useNotes();
  const { attachedNoteIds } = useChat();
  const [filter, setFilter] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setFilter("");
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  if (!open) return null;

  const attachedSet = new Set(attachedNoteIds);
  const available = notes
    .filter((n) => !n.deleted_at && !attachedSet.has(n.id))
    .filter((n) =>
      (n.title || "").toLowerCase().includes(filter.toLowerCase()),
    )
    .slice(0, 10);

  return (
    <div className="absolute bottom-full left-0 mb-1 w-64 rounded-md border bg-popover p-1 shadow-md z-50">
      <input
        ref={inputRef}
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
        }}
        placeholder={t("common.search") + "..."}
        className="w-full rounded border-none bg-transparent px-2 py-1 text-xs outline-none placeholder:text-muted-foreground"
      />
      <div className="mt-1 max-h-40 overflow-y-auto">
        {available.length === 0 ? (
          <p className="px-2 py-2 text-xs text-muted-foreground">
            {t("common.noResults")}
          </p>
        ) : (
          available.map((note) => (
            <button
              key={note.id}
              onClick={() => {
                onPick(note.id);
                onClose();
              }}
              className="flex w-full items-center rounded-sm px-2 py-1.5 text-xs hover:bg-accent truncate"
            >
              {note.title || t("common.untitled")}
            </button>
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ChatPanel
// ---------------------------------------------------------------------------

export function ChatPanel() {
  const { t } = useI18n();
  const {
    sessions,
    currentSessionId,
    messages,
    streamingText,
    isStreaming,
    attachedNoteIds,
    setChatOpen,
    attachNote,
    detachNote,
    fetchSessions,
    selectSession,
    createSession,
    deleteSession,
    sendMessage,
    cancelGeneration,
  } = useChat();
  const { notes } = useNotes();

  const [input, setInput] = useState("");
  const [showSessions, setShowSessions] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Auto-scroll on new messages or streaming
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingText]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height =
        Math.min(inputRef.current.scrollHeight, 120) + "px";
    }
  }, [input]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || isStreaming) return;
    sendMessage(text);
    setInput("");
  }, [input, isStreaming, sendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const currentTitle =
    sessions.find((s) => s.id === currentSessionId)?.title ||
    t("chat.newSession");

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 h-12 shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">{t("chat.title")}</h2>
          {currentSessionId && (
            <span className="text-[11px] text-muted-foreground truncate max-w-[140px]">
              {currentTitle}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-7 w-7">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem
                onClick={() => setShowSessions(!showSessions)}
              >
                {t("chat.sessions")}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => createSession()}>
                <Plus className="mr-2 h-3.5 w-3.5" />
                {t("chat.newSession")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setChatOpen(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Separator />

      {/* Sessions list (collapsible) */}
      {showSessions && (
        <>
          <div className="max-h-40 overflow-y-auto">
            {sessions.length === 0 ? (
              <p className="px-4 py-3 text-xs text-muted-foreground">
                {t("common.noResults")}
              </p>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  className={cn(
                    "group flex items-center gap-2 px-4 py-2 cursor-pointer text-sm transition-colors",
                    s.id === currentSessionId
                      ? "bg-accent"
                      : "hover:bg-accent/50",
                  )}
                  onClick={() => {
                    selectSession(s.id);
                    setShowSessions(false);
                  }}
                >
                  <span className="flex-1 truncate text-xs">
                    {s.title || t("chat.newSession")}
                  </span>
                  <button
                    className="shrink-0 opacity-0 group-hover:opacity-100 p-0.5 hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSession(s.id);
                    }}
                    title={t("chat.deleteSession")}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              ))
            )}
          </div>
          <Separator />
        </>
      )}

      {/* Messages area */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="flex flex-col gap-3 p-4">
          {messages.length === 0 && !streamingText && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <p className="text-sm text-muted-foreground mb-1">
                {t("chat.emptyTitle")}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("chat.emptyHint")}
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <ChatMessageBubble key={msg.id} message={msg} />
          ))}

          {/* Streaming indicator */}
          {isStreaming && streamingText && (
            <div className="flex gap-2">
              <div className="rounded-lg bg-muted px-3 py-2 text-sm max-w-[85%] whitespace-pre-wrap">
                {streamingText}
                <span className="inline-block w-1.5 h-4 bg-primary/70 animate-pulse ml-0.5 align-text-bottom" />
              </div>
            </div>
          )}

          {isStreaming && !streamingText && (
            <div className="flex gap-2">
              <div className="rounded-lg bg-muted px-3 py-2 text-sm">
                <span className="flex gap-1">
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  />
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                </span>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      <Separator />

      {/* Input area — drop zone for notes */}
      <div
        className={cn(
          "shrink-0 p-3 space-y-2 transition-colors",
          dragOver && "bg-primary/5 ring-1 ring-inset ring-primary/30 rounded-md",
        )}
        onDragOver={(e) => {
          if (e.dataTransfer.types.includes("application/nocturn-note-id")) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
            setDragOver(true);
          }
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          const noteId = e.dataTransfer.getData("application/nocturn-note-id");
          if (noteId) {
            e.preventDefault();
            attachNote(noteId);
          }
          setDragOver(false);
        }}
      >
        {/* Attached notes indicator */}
        {attachedNoteIds.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {attachedNoteIds.map((noteId) => {
              const noteName =
                notes.find((n) => n.id === noteId)?.title?.trim() ||
                t("common.untitled");
              return (
                <div
                  key={noteId}
                  className="flex items-center gap-1.5 text-xs text-primary bg-primary/10 rounded px-2 py-1"
                >
                  <Paperclip className="h-3 w-3 shrink-0" />
                  <span className="truncate max-w-[120px]">{noteName}</span>
                  <button
                    onClick={() => detachNote(noteId)}
                    className="ml-auto shrink-0 hover:text-primary/70"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              );
            })}
          </div>
        )}

        <div className="relative flex items-end gap-2">
          {/* Note picker button */}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={() => setShowPicker(!showPicker)}
            title={t("chat.attachNote")}
          >
            <Plus className="h-4 w-4" />
          </Button>

          <NotePicker
            open={showPicker}
            onClose={() => setShowPicker(false)}
            onPick={attachNote}
          />

          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("chat.inputPlaceholder")}
            rows={1}
            className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring placeholder:text-muted-foreground"
          />
          {isStreaming ? (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={cancelGeneration}
              title={t("chat.stop")}
            >
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              variant="default"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={handleSend}
              disabled={!input.trim()}
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
