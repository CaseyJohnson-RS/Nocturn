import ru from "./ru";
import en from "./en";

export type TranslationKey = keyof typeof ru;
export type Locale = "ru" | "en";

const translations: Record<Locale, Record<TranslationKey, string>> = { ru, en };

export function getTranslation(locale: Locale, key: TranslationKey, params?: Record<string, string | number>): string {
  let text = translations[locale][key] ?? translations.ru[key] ?? key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(`{${k}}`, String(v));
    }
  }
  return text;
}

export function detectLocale(): Locale {
  const stored = localStorage.getItem("nocturn.locale");
  if (stored === "ru" || stored === "en") return stored;
  const browser = navigator.language.slice(0, 2);
  return browser === "en" ? "en" : "ru";
}
