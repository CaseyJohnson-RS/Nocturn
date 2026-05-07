import { ru } from './ru';
import { en } from './en';
import type { Strings } from './ru';

function detectLocale(): 'ru' | 'en' {
  const lang = navigator.language ?? '';
  return lang.startsWith('ru') ? 'ru' : 'en';
}

const locales: Record<'ru' | 'en', Strings> = { ru, en };

let current: 'ru' | 'en' = detectLocale();

export function getLocale() {
  return current;
}

export function setLocale(locale: 'ru' | 'en') {
  current = locale;
}

export function t(): Strings {
  return locales[current];
}

export type { Strings };
