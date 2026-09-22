// Synchronous on purpose (unlike ce-kit's async storage adapter): the locale must be known before
// first paint or the UI flashes English. Storage can throw (private mode, blocked site data), in
// which case an explicit choice simply lasts for the page's lifetime.
export const LOCALE_STORAGE_KEY = "anytoolai.ui_locale";

// Code review finding: a failed `setItem` was swallowed with no fallback of its own, so the choice
// only survived in `LocaleProvider`'s own React state -- a remount within the same page load (e.g.
// `ProductPageShell` unmounting when `productId` changes) re-resolved from storage, silently losing
// it. Module-level like `getClientStorage`'s per-client storage cache, for the same reason: it must
// outlive any single component instance. There is exactly one of these per tab (unlike per-client
// storage), so it needs no keying.
let unpersistedLocale: string | null = null;

export function readStoredLocale(): string | null {
  try {
    return window.localStorage.getItem(LOCALE_STORAGE_KEY) ?? unpersistedLocale;
  } catch {
    return unpersistedLocale;
  }
}

export function writeStoredLocale(locale: string): void {
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    unpersistedLocale = locale;
  }
}

/** Test-only: `unpersistedLocale` is module-level (see above), so a test that simulates a broken
 * `setItem` must clear it afterward or it would otherwise leak into a later test in the same file. */
export function resetUnpersistedLocaleForTests(): void {
  unpersistedLocale = null;
}
