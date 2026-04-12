import { useCallback, useMemo, useRef } from "react";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/stores/i18n";
import { wordDiff } from "@/lib/diff";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DiffViewProps {
  originalContent: string;
  proposedContent: string;
  summary: string | null;
  onApply: (finalContent: string) => void;
  onDismiss: () => void;
}

// ---------------------------------------------------------------------------
// Editable insert span
// ---------------------------------------------------------------------------

function InsertSpan({
  text,
  index,
  onEdit,
}: {
  text: string;
  index: number;
  onEdit: (index: number, value: string) => void;
}) {
  const ref = useRef<HTMLSpanElement>(null);

  const handleInput = useCallback(() => {
    if (ref.current) {
      onEdit(index, ref.current.textContent || "");
    }
  }, [index, onEdit]);

  return (
    <span
      ref={ref}
      contentEditable
      suppressContentEditableWarning
      onInput={handleInput}
      className="bg-green-500/20 rounded-sm outline-none focus:ring-1 focus:ring-green-500/40"
      spellCheck={false}
    >
      {text}
    </span>
  );
}

// ---------------------------------------------------------------------------
// DiffView
// ---------------------------------------------------------------------------

export function DiffView({
  originalContent,
  proposedContent,
  summary,
  onApply,
  onDismiss,
}: DiffViewProps) {
  const { t } = useI18n();
  const segments = useMemo(
    () => wordDiff(originalContent, proposedContent),
    [originalContent, proposedContent],
  );

  // Track user edits to insert segments
  const editedInserts = useRef<Map<number, string>>(new Map());

  const handleEdit = useCallback((index: number, value: string) => {
    editedInserts.current.set(index, value);
  }, []);

  const handleApply = useCallback(() => {
    // Reconstruct final content from equal + insert (with edits)
    let text = "";
    let insertIdx = 0;
    for (const seg of segments) {
      if (seg.type === "equal") {
        text += seg.text;
      } else if (seg.type === "insert") {
        text += editedInserts.current.get(insertIdx) ?? seg.text;
        insertIdx++;
      }
      // skip "delete" segments
    }
    onApply(text);
  }, [segments, onApply]);

  // Render segments
  let insertIdx = 0;
  const rendered = segments.map((seg, i) => {
    switch (seg.type) {
      case "equal":
        return <span key={i}>{seg.text}</span>;
      case "delete":
        return (
          <span
            key={i}
            className="bg-red-500/20 line-through text-muted-foreground"
          >
            {seg.text}
          </span>
        );
      case "insert": {
        const idx = insertIdx++;
        return (
          <InsertSpan key={i} text={seg.text} index={idx} onEdit={handleEdit} />
        );
      }
    }
  });

  return (
    <div className="flex flex-1 flex-col min-h-0">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-card/50 shrink-0">
        <div className="flex-1 min-w-0">
          {summary && (
            <p className="text-sm text-muted-foreground truncate">{summary}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="default"
            size="sm"
            className="h-7 gap-1.5"
            onClick={handleApply}
          >
            <Check className="h-3.5 w-3.5" />
            {t("diff.apply")}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5"
            onClick={onDismiss}
          >
            <X className="h-3.5 w-3.5" />
            {t("diff.dismiss")}
          </Button>
        </div>
      </div>

      {/* Diff content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div
          className="whitespace-pre-wrap text-[15px] leading-[1.7] font-[Inter,system-ui,sans-serif]"
          style={{ wordBreak: "break-word" }}
        >
          {rendered}
        </div>
      </div>
    </div>
  );
}
