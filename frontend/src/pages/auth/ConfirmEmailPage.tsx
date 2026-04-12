import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiPost } from "@/api/client";
import { useI18n } from "@/stores/i18n";
import { Button } from "@/components/ui/button";

export default function ConfirmEmailPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useI18n();
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading",
  );
  const [message, setMessage] = useState("");

  useEffect(() => {
    const confirmEmail = async () => {
      const token = searchParams.get("token");

      if (!token) {
        setStatus("error");
        setMessage(t("auth.tokenMissing"));
        return;
      }

      try {
        await apiPost("/api/auth/confirm-email", { token });
        setStatus("success");
        setMessage(t("auth.emailConfirmedSuccess"));
        setTimeout(() => navigate("/login"), 2000);
      } catch (error: unknown) {
        setStatus("error");
        const detail =
          error && typeof error === "object" && "detail" in error
            ? (error as { detail: string }).detail
            : null;
        setMessage(detail || t("auth.confirmFailed"));
      }
    };

    confirmEmail();
  }, [searchParams, navigate, t]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-8 shadow-lg">
        <h1 className="text-2xl font-bold text-foreground">
          {t("auth.confirmEmailTitle")}
        </h1>

        {status === "loading" && (
          <div className="mt-6 text-center text-muted-foreground">
            <div className="mb-4">{t("auth.confirming")}</div>
            <div className="h-2 w-8 animate-pulse rounded bg-muted-foreground/50 mx-auto" />
          </div>
        )}

        {status === "success" && (
          <div className="mt-6">
            <div className="rounded-lg bg-green-500/10 p-4 text-green-500">
              {message}
            </div>
            <div className="mt-4 text-center text-sm text-muted-foreground">
              {t("auth.redirecting")}
            </div>
          </div>
        )}

        {status === "error" && (
          <div className="mt-6">
            <div className="rounded-lg bg-destructive/10 p-4 text-destructive">
              {message}
            </div>
            <div className="mt-6 flex gap-3">
              <Button
                onClick={() => navigate("/login")}
                variant="outline"
                className="flex-1"
              >
                {t("auth.backToLogin")}
              </Button>
              <Button
                onClick={() => navigate("/register")}
                className="flex-1"
              >
                {t("auth.registerAgain")}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
