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
