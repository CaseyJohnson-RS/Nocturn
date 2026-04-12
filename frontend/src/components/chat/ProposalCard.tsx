import { useState } from "react";
import {
  Check,
  X,
  FileEdit,
  FilePlus,
  Trash2,
  Tag,
  Loader2,
  Eye,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useChat } from "@/stores/chat";
import { useNotes } from "@/stores/notes";
import { useTabs } from "@/stores/tabs";
import { useI18n } from "@/stores/i18n";
import type { Proposal } from "@/api/types";
import * as notesApi from "@/api/notes";
import { cn } from "@/lib/utils";

const PROPOSAL_ICONS: Record<string, typeof FileEdit> = {
  edit_note: FileEdit,
  create_note: FilePlus,
  delete_note: Trash2,
  add_tags: Tag,
  remove_tags: Tag,
};

const PROPOSAL_LABEL_KEYS: Record<string, string> = {
  edit_note: "proposal.editNote",
  create_note: "proposal.createNote",
  delete_note: "proposal.deleteNote",
  add_tags: "proposal.addTags",
  remove_tags: "proposal.removeTags",
};

interface ProposalCardProps {
  messageId: string;
  proposal: Proposal;
}

export function ProposalCard({ messageId, proposal }: ProposalCardProps) {
  const { t } = useI18n();
  const { applyAction, dismissAction } = useChat();
  const { fetchNotes } = useNotes();
  const { openNote, closeNoteTab } = useTabs();
  const [loading, setLoading] = useState(false);

  const Icon = PROPOSAL_ICONS[proposal.proposal_type] ?? FileEdit;
  const labelKey = PROPOSAL_LABEL_KEYS[proposal.proposal_type];
  const label = labelKey ? t(labelKey as Parameters<typeof t>[0]) : proposal.proposal_type;
  const isPending = proposal.status === "pending";
  const isApplied = proposal.status === "applied";
  const isDismissed = proposal.status === "dismissed";

  const handleApply = async () => {
    setLoading(true);
    try {
      if (proposal.data) {
        switch (proposal.proposal_type) {
          case "edit_note":
            if (proposal.note_id) {
              await notesApi.updateNote(proposal.note_id, {
                title: proposal.data.title as string | undefined,
                content: proposal.data.content as string | undefined,
                version: (proposal.data.version as number) ?? 1,
              });
            }
            break;
          case "create_note": {
            const created = await notesApi.createNote({
              title: proposal.data.title as string,
              content: proposal.data.content as string,
            });
            openNote(created.id, created.title || undefined);
            break;
          }
          case "delete_note":
            if (proposal.note_id) {
              await notesApi.deleteNote(proposal.note_id);
              closeNoteTab(proposal.note_id);
            }
            break;
          case "add_tags":
          case "remove_tags":
            if (proposal.note_id && proposal.data.tag_ids) {
              await notesApi.updateNoteTags(
                proposal.note_id,
                proposal.data.tag_ids as string[],
              );
            }
            break;
        }
      }
      await applyAction(messageId, proposal.id);
      await fetchNotes();
    } catch (err) {
      console.error("Failed to apply proposal:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDismiss = async () => {
    setLoading(true);
    try {
      await dismissAction(messageId, proposal.id);
    } finally {
      setLoading(false);
    }
  };

  const preview = isPending ? getPreview(proposal) : null;

  return (
    <div
      className={cn(
        "rounded-md border text-xs",
        isPending && "border-primary/30 bg-primary/5",
        isApplied && "border-green-500/30 bg-green-500/5",
        isDismissed && "border-border bg-muted/30 opacity-60",
      )}
    >
      <div className="flex items-center gap-2 px-3 py-2">
        <Icon
          className={cn(
            "h-3.5 w-3.5 shrink-0",
            isPending && "text-primary",
            isApplied && "text-green-500",
            isDismissed && "text-muted-foreground",
          )}
        />
        <span className="flex-1 font-medium truncate">{label}</span>

        {isPending && !loading && (
          <div className="flex items-center gap-1">
            {proposal.proposal_type === "edit_note" && proposal.note_id && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-primary hover:text-primary/80 hover:bg-primary/10"
                onClick={() => openNote(proposal.note_id!, undefined)}
                title={t("proposal.preview")}
              >
                <Eye className="h-3.5 w-3.5" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-green-500 hover:text-green-400 hover:bg-green-500/10"
              onClick={handleApply}
              title={t("common.apply")}
            >
              <Check className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-foreground"
              onClick={handleDismiss}
              title={t("common.dismiss")}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}

        {loading && (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
        )}

        {isApplied && (
          <span className="text-green-500 text-[10px]">
            {t("proposal.applied")}
          </span>
        )}
        {isDismissed && (
          <span className="text-muted-foreground text-[10px]">
            {t("proposal.dismissed")}
          </span>
        )}
      </div>

      {preview && (
        <div className="px-3 pb-2 text-muted-foreground">
          <p className="truncate">{preview}</p>
        </div>
      )}

      {proposal.summary && !isPending && (
        <div className="px-3 pb-2 text-muted-foreground">
          <p className="truncate">{proposal.summary}</p>
        </div>
      )}
    </div>
  );
}

function getPreview(proposal: Proposal): string | null {
  if (!proposal.data) return null;
  switch (proposal.proposal_type) {
    case "edit_note": {
      const title = proposal.data.title as string | undefined;
      const content = proposal.data.content as string | undefined;
      if (title && content) return title;
      if (title) return title;
      if (content) return content.slice(0, 80) + "...";
      return null;
    }
    case "create_note":
      return (proposal.data.title as string) || null;
    case "delete_note":
      return proposal.summary || null;
    case "add_tags":
    case "remove_tags":
      return null;
    default:
      return null;
  }
}
