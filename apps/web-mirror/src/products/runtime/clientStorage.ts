import { createInMemoryAsyncStorage, createWindowLocalStorageAdapter, type AsyncStorage, type PlatformApiClient } from "@anytoolai/ce-kit";

/**
 * `primary` (normally `window.localStorage`, shared across tabs) with an in-memory safety net, so a
 * value stays stable for the page's lifetime even when the primary can't hold it.
 *
 * ce-kit deliberately treats a failed read as a cache miss and a failed write as best-effort, so
 * without this a guest id (or `web_session_id`) the storage can't hold would be minted anew on every
 * remount. Memory is therefore a complete last-known-good copy of what this page has read or written.
 *
 * The one invariant everything below serves: a key is *stale* when the primary may hold a value
 * OLDER than memory's. Only a failed write or removal can make it so (memory took the new value, the
 * primary didn't). A failed read cannot -- it produced no value, so ce-kit is free to retry it (it
 * re-reads after minting a guest precisely because a read failure may be transient) -- and a
 * successful write or removal ends staleness, since the primary then matches memory again.
 *
 * - Reads and writes go to the primary first, so cross-tab sharing is unchanged while it works, and
 *   every successful read is mirrored into memory, so a value only ever *read* (a guest id persisted
 *   by an earlier visit) survives the primary breaking later.
 * - A read that misses or fails is answered from memory for that call only; it changes no state.
 * - A stale key is never read from the primary: that could bring back a value already superseded (a
 *   guest id `refreshGuestIdentity()` just healed). Staleness is per key, so a write failing for one
 *   key (quota exceeded on `web_session_id`) does not affect the guest id.
 * - The primary is still written on every mutation, stale or not, so a recovered storage catches up.
 * - `remove()` never throws, so a self-heal always sticks.
 */
export function createResilientStorage(primary: AsyncStorage | null, memory: AsyncStorage): AsyncStorage {
  if (primary === null) {
    return memory;
  }
  const staleKeys = new Set<string>();

  async function mutatePrimary(key: string, mutation: () => Promise<void>): Promise<void> {
    try {
      await mutation();
      staleKeys.delete(key);
    } catch {
      staleKeys.add(key);
    }
  }

  return {
    async get(key) {
      if (!staleKeys.has(key)) {
        try {
          const stored = await primary.get(key);
          if (stored !== undefined) {
            await memory.set(key, stored);
            return stored;
          }
        } catch {
          // Possibly transient -- answer from memory for this call only.
        }
      }
      return memory.get(key);
    },
    async set(key, value) {
      await memory.set(key, value);
      await mutatePrimary(key, () => primary.set(key, value));
    },
    async remove(key) {
      await memory.remove(key);
      await mutatePrimary(key, () => primary.remove(key));
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
