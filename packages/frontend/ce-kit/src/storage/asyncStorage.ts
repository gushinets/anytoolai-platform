/**
 * Injectable async key-value storage contract. Its shape matches the promise-based
 * `chrome.storage.local` API (`get`/`set`/`remove` on a single key), so a Chrome extension can
 * satisfy it with a thin wrapper around `chrome.storage.local` without CE-kit depending on
 * `@types/chrome` itself.
 */
export type AsyncStorage = {
  get(key: string): Promise<string | undefined>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
};
