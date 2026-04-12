import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/stores/auth";
import LoginPage from "@/pages/auth/LoginPage";
import RegisterPage from "@/pages/auth/RegisterPage";
import ConfirmEmailPage from "@/pages/auth/ConfirmEmailPage";
import ForgotPasswordPage from "@/pages/auth/ForgotPasswordPage";
import AppLayout from "@/layouts/AppLayout";

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function GuestOnly({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (user) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <GuestOnly>
            <LoginPage />
          </GuestOnly>
        }
      />
      <Route
        path="/register"
        element={
          <GuestOnly>
            <RegisterPage />
          </GuestOnly>
        }
      />
      <Route
        path="/confirm-email"
        element={<ConfirmEmailPage />}
      />
      <Route
        path="/forgot-password"
        element={
          <GuestOnly>
            <ForgotPasswordPage />
          </GuestOnly>
        }
      />
      <Route
        path="/*"
        element={
          <AuthGuard>
            <AppLayout />
          </AuthGuard>
        }
      />
    </Routes>
  );
}
