import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "@/stores/i18n";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { requestPasswordReset } from "@/api/auth";
import { ApiError } from "@/api/client";

export default function ForgotPasswordPage() {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
      else setError(t("auth.sendFailed"));
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="w-full max-w-sm space-y-4 p-6 text-center">
          <h1 className="text-2xl font-bold">{t("auth.linkSent")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("auth.linkSentText", { email })}
          </p>
          <Link to="/login">
            <Button variant="outline" className="w-full mt-2">
              {t("auth.backToLogin")}
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-6 p-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight">
            {t("auth.resetPasswordTitle")}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("auth.resetSubtitle")}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          <div className="space-y-2">
            <label className="text-sm font-medium">{t("auth.email")}</label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email@example.com"
              required
              autoFocus
            />
          </div>

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? t("auth.sending") : t("auth.sendLink")}
          </Button>
        </form>

        <p className="text-center text-sm">
          <Link
            to="/login"
            className="text-muted-foreground hover:underline"
          >
            {t("auth.backToLogin")}
          </Link>
        </p>
      </div>
    </div>
  );
}
