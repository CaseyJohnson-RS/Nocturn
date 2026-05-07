import { t, getLocale, setLocale } from '@/i18n';
import { ru } from '@/i18n/ru';
import { en } from '@/i18n/en';

beforeEach(() => {
  setLocale('en');
});

describe('i18n – locale switching', () => {
  it('getLocale returns the current locale', () => {
    setLocale('ru');
    expect(getLocale()).toBe('ru');
  });

  it('t() returns English strings after setLocale("en")', () => {
    setLocale('en');
    expect(t().auth.login).toBe('Sign in');
  });

  it('t() returns Russian strings after setLocale("ru")', () => {
    setLocale('ru');
    expect(t().auth.login).toBe('Войти');
  });

  it('switches between locales multiple times', () => {
    setLocale('ru');
    expect(t().common.loading).toBe('Загрузка...');
    setLocale('en');
    expect(t().common.loading).toBe('Loading...');
  });
});

// Walk a nested string-valued object and collect dot-paths like "auth.login"
function collectKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([key, val]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return typeof val === 'object' && val !== null
      ? collectKeys(val as Record<string, unknown>, path)
      : [path];
  });
}

describe('i18n – key parity', () => {
  it('en and ru have exactly the same keys', () => {
    const enKeys = collectKeys(en as unknown as Record<string, unknown>).sort();
    const ruKeys = collectKeys(ru as unknown as Record<string, unknown>).sort();
    expect(enKeys).toEqual(ruKeys);
  });

  it('all string values in en are non-empty', () => {
    function checkNonEmpty(obj: Record<string, unknown>, path = '') {
      for (const [k, v] of Object.entries(obj)) {
        const p = path ? `${path}.${k}` : k;
        if (typeof v === 'object' && v !== null) {
          checkNonEmpty(v as Record<string, unknown>, p);
        } else {
          expect(String(v), `en.${p} should not be empty`).not.toBe('');
        }
      }
    }
    checkNonEmpty(en as unknown as Record<string, unknown>);
  });

  it('all string values in ru are non-empty', () => {
    function checkNonEmpty(obj: Record<string, unknown>, path = '') {
      for (const [k, v] of Object.entries(obj)) {
        const p = path ? `${path}.${k}` : k;
        if (typeof v === 'object' && v !== null) {
          checkNonEmpty(v as Record<string, unknown>, p);
        } else {
          expect(String(v), `ru.${p} should not be empty`).not.toBe('');
        }
      }
    }
    checkNonEmpty(ru as unknown as Record<string, unknown>);
  });
});
