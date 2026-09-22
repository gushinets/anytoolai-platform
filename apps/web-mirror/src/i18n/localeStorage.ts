// Synchronous on purpose (unlike ce-kit's async storage adapter): the locale must be known before
// first paint or the UI flashes English. Storage can throw (private mode, blocked site data), in
// which case an explicit choice simply lasts for the page's lifetime.
const STORAGE_KEY = "anytoolai.ui_locale";

export function readStoredLocale(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function writeStoredLocale(locale: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // unavailable storage: the in-memory choice in LocaleProvider still applies.
  }
}
