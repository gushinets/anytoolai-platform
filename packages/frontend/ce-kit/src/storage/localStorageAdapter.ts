import type { AsyncStorage } from "./asyncStorage";

/**
 * Adapts `window.localStorage` (sync, browser-only) to the async `AsyncStorage` contract.
 *
 * Parameter named `backingStorage`, not `storage` -- a bare `storage` identifier is what WXT's
 * global auto-import scans for (`wxt/utils/storage`) when this workspace package is bundled
 * directly into a Chrome-extension build, and its regex-based scan isn't scope-aware enough to
 * see this is a local parameter, not that global.
 */
export function createLocalStorageAdapter(backingStorage: Storage): AsyncStorage {
  return {
    async get(key) {
      return backingStorage.getItem(key) ?? undefined;
    },
    async set(key, value) {
      backingStorage.setItem(key, value);
    },
    async remove(key) {
      backingStorage.removeItem(key);
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
