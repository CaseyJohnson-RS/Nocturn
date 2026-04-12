import { Paperclip } from "lucide-react";
import type { ChatMessage, Action } from "@/api/types";
import { ProposalCard } from "./ProposalCard";
import { PendingConfirmationCard } from "./PendingConfirmationCard";
import { useNotes } from "@/stores/notes";
import { useI18n } from "@/stores/i18n";
import { useTabs } from "@/stores/tabs";
import { cn } from "@/lib/utils";

interface ChatMessageBubbleProps {
  message: ChatMessage;
}

export function ChatMessageBubble({ message }: ChatMessageBubbleProps) {
  const { t } = useI18n();
  const { notes } = useNotes();
  const { openNote } = useTabs();
  const isUser = message.role === "user";
  const actions = message.actions ?? [];
  const attachedIds = message.attached_note_ids ?? [];

  return (
    <div className={cn("flex flex-col gap-2", isUser && "items-end")}>
      {/* Attached note chips */}
      {attachedIds.length > 0 && (
        <div className={cn("flex flex-wrap gap-1", isUser && "justify-end")}>
          {attachedIds.map((noteId) => {
            const note = notes.find((n) => n.id === noteId);
            const title = note?.title?.trim() || t("common.untitled");
            return (
              <button
                key={noteId}
                onClick={() => openNote(noteId, note?.title || undefined)}
                className="flex items-center gap-1 rounded bg-primary/10 px-2 py-0.5 text-[11px] text-primary hover:bg-primary/20 transition-colors"
              >
                <Paperclip className="h-2.5 w-2.5" />
                <span className="truncate max-w-[120px]">{title}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Text bubble */}
      {message.content && (
        <div
          className={cn(
            "rounded-lg px-3 py-2 text-sm max-w-[85%] whitespace-pre-wrap",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-foreground",
          )}
        >
          {message.content}
        </div>
      )}

      {/* Action cards */}
      {actions.length > 0 && (
        <div className="flex flex-col gap-1.5 w-full">
          {actions.map((action: Action) =>
            action.type === "proposal" ? (
              <ProposalCard
                key={action.id}
                messageId={message.id}
                proposal={action}
              />
            ) : action.type === "pending_confirmation" ? (
              <PendingConfirmationCard
                key={action.id}
                messageId={message.id}
                confirmation={action}
              />
            ) : null,
          )}
        </div>
      )}
    </div>
  );
}
