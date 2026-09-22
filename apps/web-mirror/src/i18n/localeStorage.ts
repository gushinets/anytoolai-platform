// Synchronous on purpose (unlike ce-kit's async storage adapter): the locale must be known before
// first paint or the UI flashes English. Storage can throw (private mode, blocked site data), in
// which case an explicit choice simply lasts for the page's lifetime.
export const LOCALE_STORAGE_KEY = "anytoolai.ui_locale";

/**
 * Mirrors `clientStorage.ts`'s staleness tracking, for the same reason and at the same (single-key)
 * granularity: once `setItem` fails, `localStorage` may hold a value OLDER than what was just
 * asked to persist (an earlier explicit choice, or nothing) -- reading it back would silently
 * resurrect that stale value instead of the newer, failed write.
 *
 * Code review finding: an earlier version answered `getItem() ?? lastWrittenLocale`, which only
 * covered the case where `getItem()` itself returned null (no explicit choice ever stored). If
 * storage already held an older explicit choice (e.g. "en") and a newer write ("fr") then failed,
 * `getItem()` still returned that non-null "en", so the fallback was never consulted and a remount
 * silently reverted the UI to the stale, no-longer-current choice. `isStale` makes a failed write
 * stop trusting the primary for this key at all -- not just when it happens to read back null --
 * until a later write succeeds and the primary matches memory again.
 *
 * `lastWrittenLocale` is set on every write regardless of outcome (not only on failure): it doubles
 * as the answer for a transient read failure while not stale, mirroring `clientStorage.ts`'s "read
 * failure answered from memory for that call only" contract.
 */
let lastWrittenLocale: string | null = null;
let isStale = false;

export function readStoredLocale(): string | null {
  if (!isStale) {
    try {
      return window.localStorage.getItem(LOCALE_STORAGE_KEY) ?? lastWrittenLocale;
    } catch {
      // Possibly transient -- answer from memory for this call only, below.
    }
  }
  return lastWrittenLocale;
}

export function writeStoredLocale(locale: string): void {
  lastWrittenLocale = locale;
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    isStale = false;
  } catch {
    isStale = true;
  }
}

/** Test-only: the state above is module-level (see above), so a test that simulates a broken
 * `setItem` must clear it afterward or it would otherwise leak into a later test in the same file. */
export function resetUnpersistedLocaleForTests(): void {
  lastWrittenLocale = null;
  isStale = false;
}
