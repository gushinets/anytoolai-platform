import type { AsyncStorage } from "./asyncStorage";

/**
 * Structural subset of `chrome.storage.local`'s promise-based API (the modern MV3 calling
 * convention: call `get`/`set`/`remove` without a callback and get a Promise back) that this
 * adapter actually calls. `chrome.storage.local` itself satisfies this shape, so callers can pass
 * it directly without CE-kit depending on `@types/chrome`.
 */
export type ChromeStorageArea = {
  get(keys: string[]): Promise<Record<string, unknown>>;
  set(items: Record<string, unknown>): Promise<void>;
  remove(keys: string[]): Promise<void>;
};

/** Adapts `chrome.storage.local` (multi-key, untyped-value) to the single-key `AsyncStorage` contract. */
export function createChromeStorageAdapter(area: ChromeStorageArea): AsyncStorage {
  return {
    async get(key) {
      const result = await area.get([key]);
      const value = result[key];
      return typeof value === "string" ? value : undefined;
    },
    async set(key, value) {
      await area.set({ [key]: value });
    },
    async remove(key) {
      await area.remove([key]);
    },
  };
}
