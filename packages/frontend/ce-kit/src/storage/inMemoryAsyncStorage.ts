import type { AsyncStorage } from "./asyncStorage";

/** In-memory `AsyncStorage` implementation for tests and non-extension hosts. */
export function createInMemoryAsyncStorage(initial: Record<string, string> = {}): AsyncStorage {
  const store = new Map(Object.entries(initial));

  return {
    async get(key) {
      return store.get(key);
    },
    async set(key, value) {
      store.set(key, value);
    },
    async remove(key) {
      store.delete(key);
    },
  };
}
