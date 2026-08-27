import type { AsyncStorage } from "./asyncStorage";

/** Adapts `window.localStorage` (sync, browser-only) to the async `AsyncStorage` contract. */
export function createLocalStorageAdapter(storage: Storage): AsyncStorage {
  return {
    async get(key) {
      return storage.getItem(key) ?? undefined;
    },
    async set(key, value) {
      storage.setItem(key, value);
    },
    async remove(key) {
      storage.removeItem(key);
    },
  };
}

/**
 * Guarded convenience wrapper around `createLocalStorageAdapter(window.localStorage)` for direct
 * browser use. Accessing the `window.localStorage` getter itself can throw synchronously (privacy-
 * hardened browsers, storage-denied sandboxed iframes, or simply no `window` at all in a
 * non-browser context) -- every caller previously had to reimplement this try/catch locally to
 * avoid an unhandled exception; centralized here so future consumers get the same protection by
 * default. Returns null (not a rejected promise) since the failure happens before any
 * `AsyncStorage` method is even reachable -- callers should treat null the same as "no persisted
 * storage available."
 */
export function createWindowLocalStorageAdapter(): AsyncStorage | null {
  try {
    return createLocalStorageAdapter(window.localStorage);
  } catch {
    return null;
  }
}
