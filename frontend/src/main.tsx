import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "@/stores/auth";
import { I18nProvider } from "@/stores/i18n";
import { ThemeProvider } from "@/stores/theme";
import { ToastProvider } from "@/stores/toast";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <I18nProvider>
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider>
              <App />
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </I18nProvider>
    </BrowserRouter>
  </StrictMode>,
);
