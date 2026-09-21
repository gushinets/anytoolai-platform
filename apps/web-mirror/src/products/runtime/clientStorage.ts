import { createInMemoryAsyncStorage, createWindowLocalStorageAdapter, type AsyncStorage, type PlatformApiClient } from "@anytoolai/ce-kit";

/**
 * `primary` (normally `window.localStorage`, shared across tabs) with an in-memory safety net, so a
 * value stays stable for the page's lifetime even when the primary can't hold it.
 *
 * Code review finding: two different ways of "no usable localStorage" both used to mint a new guest
 * (or `web_session_id`) on every remount, because ce-kit deliberately treats a failed read as a cache
 * miss and a failed write as best-effort: the getter `window.localStorage` itself throwing (handled
 * by falling back to a bare in-memory storage), and the getter working while `getItem`/`setItem`
 * throw (Safari private mode with a zero quota, storage denied after the fact) -- which wasn't.
 *
 * Reads and writes go to the primary first, so cross-tab sharing is unchanged while it works. The
 * first time any primary operation throws, the primary is no longer trusted for the rest of this
 * storage's life and memory alone is authoritative -- otherwise a value the primary failed to
 * forget (a stale guest id that `refreshGuestIdentity()` just healed) could be read straight back.
 * Writes always land in memory too, and `remove()` never throws, so a self-heal always sticks.
 */
export function createResilientStorage(primary: AsyncStorage | null, memory: AsyncStorage): AsyncStorage {
  if (primary === null) {
    return memory;
  }
  let primaryTrusted = true;
  return {
    async get(key) {
      if (primaryTrusted) {
        try {
          const stored = await primary.get(key);
          if (stored !== undefined) {
            return stored;
          }
        } catch {
          primaryTrusted = false;
        }
      }
      return memory.get(key);
    },
    async set(key, value) {
      await memory.set(key, value);
      if (primaryTrusted) {
        try {
          await primary.set(key, value);
        } catch {
          primaryTrusted = false;
        }
      }
    },
    async remove(key) {
      await memory.remove(key);
      if (primaryTrusted) {
        try {
          await primary.remove(key);
        } catch {
          primaryTrusted = false;
        }
      }
    },
  };
}

const storageByClient = new WeakMap<PlatformApiClient, AsyncStorage>();

/**
 * The one storage every mount and route-level consumer for this client shares (guest identity,
 * `web_session_id`) -- per client rather than per mount or per product, like the other per-client
 * caches in `ProductRunPage`: a mode switch remounts the page, and navigating between products
 * keeps the client, and neither may start from an empty fallback and mint a new identity or session
 * (a `web_session_id` rotates after 30 minutes of inactivity, not when the product changes).
 */
export function getClientStorage(client: PlatformApiClient): AsyncStorage {
  let storage = storageByClient.get(client);
  if (!storage) {
    storage = createResilientStorage(createWindowLocalStorageAdapter(), createInMemoryAsyncStorage());
    storageByClient.set(client, storage);
  }
  return storage;
}
