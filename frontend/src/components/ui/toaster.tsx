import { AlertTriangle, X, XCircle } from "lucide-react";
import { useToast, type ToastVariant } from "@/stores/toast";
import { cn } from "@/lib/utils";

const variantStyles: Record<ToastVariant, string> = {
  error: "border-destructive/50 bg-destructive/10 text-destructive",
  warning: "border-yellow-500/50 bg-yellow-500/10 text-yellow-400",
};

const variantIcons: Record<ToastVariant, typeof XCircle> = {
  error: XCircle,
  warning: AlertTriangle,
};

export function Toaster() {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
      {toasts.map((toast) => {
        const Icon = variantIcons[toast.variant];
        return (
          <div
            key={toast.id}
            className={cn(
              "flex items-start gap-2 rounded-lg border px-4 py-3 text-sm shadow-lg animate-in slide-in-from-bottom-2 fade-in",
              variantStyles[toast.variant],
            )}
          >
            <Icon className="h-4 w-4 mt-0.5 shrink-0" />
            <span className="flex-1">{toast.message}</span>
            <button
              onClick={() => removeToast(toast.id)}
              className="shrink-0 opacity-60 hover:opacity-100"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
