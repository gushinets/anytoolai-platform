import { createInMemoryAsyncStorage, createWindowLocalStorageAdapter, type AsyncStorage, type PlatformApiClient } from "@anytoolai/ce-kit";

/**
 * `primary` (normally `window.localStorage`, shared across tabs) with an in-memory safety net, so a
 * value stays stable for the page's lifetime even when the primary can't hold it.
 *
 * ce-kit deliberately treats a failed read as a cache miss and a failed write as best-effort, so
 * without this a guest id (or `web_session_id`) the storage can't hold would be minted anew on every
 * remount. Memory is therefore a complete last-known-good copy of what this page has read or written:
 *
 * - Reads and writes go to the primary first, so cross-tab sharing is unchanged while it works, and
 *   every successful read is mirrored into memory -- a value only ever *read* (a guest id persisted
 *   by an earlier visit) is not lost if the primary breaks later.
 * - A primary miss falls back to memory, which covers storage that accepts a write but forgets it.
 * - Trust is per key: the first failing operation on a key stops consulting the primary for that key
 *   only, so a write failing for one key (quota exceeded on `web_session_id`) can't take the guest id
 *   down with it. Not trusting it at all afterwards also means a stale value the primary failed to
 *   forget can't be read back (a guest id `refreshGuestIdentity()` just healed).
 * - `remove()` never throws, so a self-heal always sticks.
 */
export function createResilientStorage(primary: AsyncStorage | null, memory: AsyncStorage): AsyncStorage {
  if (primary === null) {
    return memory;
  }
  const untrustedKeys = new Set<string>();
  return {
    async get(key) {
      if (!untrustedKeys.has(key)) {
        try {
          const stored = await primary.get(key);
          if (stored !== undefined) {
            await memory.set(key, stored);
            return stored;
          }
        } catch {
          untrustedKeys.add(key);
        }
      }
      return memory.get(key);
    },
    async set(key, value) {
      await memory.set(key, value);
      if (!untrustedKeys.has(key)) {
        try {
          await primary.set(key, value);
        } catch {
          untrustedKeys.add(key);
        }
      }
    },
    async remove(key) {
      await memory.remove(key);
      if (!untrustedKeys.has(key)) {
        try {
          await primary.remove(key);
        } catch {
          untrustedKeys.add(key);
        }
      }
    },
  };
}

const storageByClient = new WeakMap<PlatformApiClient, AsyncStorage>();

/**
 * The one storage for this client (guest identity, `web_session_id`), so every mount and route-level
 * consumer shares it. Only as long-lived as the client itself -- see `getPlatformApiClient()`, which
 * is what makes that a page load rather than a single component mount.
 */
export function getClientStorage(client: PlatformApiClient): AsyncStorage {
  let storage = storageByClient.get(client);
  if (!storage) {
    storage = createResilientStorage(createWindowLocalStorageAdapter(), createInMemoryAsyncStorage());
    storageByClient.set(client, storage);
  }
  return storage;
}
