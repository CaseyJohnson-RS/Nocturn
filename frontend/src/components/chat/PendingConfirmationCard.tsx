import { useState } from "react";
import { AlertTriangle, Check, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useChat } from "@/stores/chat";
import { useNotes } from "@/stores/notes";
import { useI18n } from "@/stores/i18n";
import type { PendingConfirmation } from "@/api/types";
import { cn } from "@/lib/utils";

interface Props {
  messageId: string;
  confirmation: PendingConfirmation;
}

export function PendingConfirmationCard({ confirmation }: Props) {
  const { t } = useI18n();
  const { confirmBulk, dismissBulk } = useChat();
  const { fetchNotes } = useNotes();
  const [loading, setLoading] = useState(false);

  const isPending = confirmation.status === "pending";
  const isConfirmed = confirmation.status === "confirmed";
  const isDismissed = confirmation.status === "dismissed";
  const label = confirmation.summary || confirmation.operation_type;
  const count = confirmation.note_ids.length;

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await confirmBulk(confirmation.id);
      await fetchNotes();
    } catch (err) {
      console.error("Failed to confirm bulk:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDismiss = async () => {
    setLoading(true);
    try {
      await dismissBulk(confirmation.id);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className={cn(
        "rounded-md border text-xs",
        isPending && "border-yellow-500/30 bg-yellow-500/5",
        isConfirmed && "border-green-500/30 bg-green-500/5",
        isDismissed && "border-border bg-muted/30 opacity-60",
      )}
    >
      <div className="flex items-center gap-2 px-3 py-2">
        <AlertTriangle
          className={cn(
            "h-3.5 w-3.5 shrink-0",
            isPending && "text-yellow-500",
            isConfirmed && "text-green-500",
            isDismissed && "text-muted-foreground",
          )}
        />
        <div className="flex-1 min-w-0">
          <p className="font-medium">{label}</p>
          <p className="text-muted-foreground">
            {t("proposal.affectedNotes", { count })}
          </p>
        </div>

        {isPending && !loading && (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-green-500 hover:text-green-400 hover:bg-green-500/10"
              onClick={handleConfirm}
              title={t("proposal.bulkConfirm")}
            >
              <Check className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-foreground"
              onClick={handleDismiss}
              title={t("proposal.bulkDismiss")}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}

        {loading && (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
        )}

        {isConfirmed && (
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

      {confirmation.summary && !isPending && (
        <div className="px-3 pb-2 text-muted-foreground">
          <p className="truncate">{confirmation.summary}</p>
        </div>
      )}
    </div>
  );
}
