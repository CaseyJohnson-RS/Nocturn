import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/stores/auth";
import { useI18n } from "@/stores/i18n";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/api/client";

export default function LoginPage() {
  const { login } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
      else setError(t("auth.loginFailed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-6 p-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight">Nocturn</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("auth.loginSubtitle")}
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

          <div className="space-y-2">
            <label className="text-sm font-medium">{t("auth.password")}</label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("auth.enterPassword")}
              required
            />
          </div>

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? t("auth.loggingIn") : t("auth.login")}
          </Button>
        </form>

        <div className="space-y-2 text-center text-sm">
          <p>
            {t("auth.noAccount")}{" "}
            <Link to="/register" className="text-primary hover:underline">
              {t("auth.registerLink")}
            </Link>
          </p>
          <p>
            <Link
              to="/forgot-password"
              className="text-muted-foreground hover:underline"
            >
              {t("auth.forgotPassword")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
