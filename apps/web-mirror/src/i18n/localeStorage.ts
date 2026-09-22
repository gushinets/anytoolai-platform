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
 * Code review finding (round 1): an earlier version answered `getItem() ?? lastKnownLocale`, which
 * only covered the case where `getItem()` itself returned null. If storage already held an older
 * choice and a newer write then failed, `getItem()` still returned that non-null older value, so
 * the fallback was never consulted and a remount silently reverted to the stale choice. `isStale`
 * fixes that: a failed write stops trusting the primary for this key at all (not just when it
 * happens to read back null) until a later write succeeds.
 *
 * Code review finding (round 2): the round-1 fix over-corrected -- it also used `lastKnownLocale`
 * as a fallback for a *successful* read that legitimately returned null (the key genuinely removed
 * or never set), resurrecting a locale written earlier in the same page load when the correct
 * result is "no explicit choice", i.e. fall through to the browser language. Only a read that
 * *fails* (the catch below) or a write that fails (`isStale`) means the primary's true state is
 * unknown; a successful read, even a null one, IS the true state and must be trusted, not
 * overridden. Every successful read is mirrored into `lastKnownLocale` (matching
 * `clientStorage.ts`'s own "every successful read is mirrored into memory" rule), so a later
 * transient read failure is answered by what storage most recently and genuinely said, not by a
 * possibly much older write.
 */
let lastKnownLocale: string | null = null;
let isStale = false;

export function readStoredLocale(): string | null {
  if (isStale) {
    return lastKnownLocale;
  }
  try {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    lastKnownLocale = stored;
    return stored;
  } catch {
    // Possibly transient -- answer from memory for this call only; a failed *read* never marks the
    // key stale (it produced no value to distrust the primary over -- the next call is free to
    // retry it, same as `clientStorage.ts`'s own read-failure contract).
    return lastKnownLocale;
  }
}

export function writeStoredLocale(locale: string): void {
  lastKnownLocale = locale;
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
  lastKnownLocale = null;
  isStale = false;
}
