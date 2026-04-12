import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface ResizeHandleProps {
  /** Direction the handle resizes. "left" shrinks the left panel, "right" shrinks the right panel. */
  direction: "left" | "right";
  onResize: (delta: number) => void;
}

export function ResizeHandle({ direction, onResize }: ResizeHandleProps) {
  const [dragging, setDragging] = useState(false);
  const startX = useRef(0);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      startX.current = e.clientX;
      setDragging(true);
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging) return;
      const delta = e.clientX - startX.current;
      startX.current = e.clientX;
      onResize(direction === "left" ? delta : -delta);
    },
    [dragging, direction, onResize],
  );

  const handlePointerUp = useCallback(() => {
    setDragging(false);
  }, []);

  // Prevent text selection while dragging
  useEffect(() => {
    if (dragging) {
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    } else {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [dragging]);

  return (
    <div
      className={cn(
        "shrink-0 w-1 cursor-col-resize hover:bg-primary/30 transition-colors",
        dragging && "bg-primary/40",
      )}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    />
  );
}
