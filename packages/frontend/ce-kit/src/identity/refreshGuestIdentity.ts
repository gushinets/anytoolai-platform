import type { PlatformApiClient } from "../api/client";
import type { AsyncStorage } from "../storage/asyncStorage";
import { createInMemoryAsyncStorage } from "../storage/inMemoryAsyncStorage";
import { DEFAULT_GUEST_STORAGE_KEY, type GuestIdentityResult } from "./guestIdentity";

export type RefreshGuestIdentityOptions = {
  storageKey?: string;
  /** Used for this mint only if clearing `backingStorage` itself fails. Defaults to a fresh
   * in-memory adapter, not `backingStorage` itself -- a failed removal can't be trusted to have
   * actually forgotten the stale id, so falling back to `backingStorage` would silently defeat the
   * whole point of this function: `createGuestIdentity()` would just read the same stale id
   * straight back out of it. A caller may still pass its own (e.g. one it already keeps around for
   * other storage-unavailable fallbacks) to avoid an extra throwaway adapter/identity per heal. */
  fallbackStorage?: AsyncStorage;
};

/**
 * Clears whatever guest id is currently persisted in `backingStorage` and mints a fresh one -- the
 * self-heal for a guest id the backend no longer recognizes (`isHandoffGuestIdentityInvalid()` on
 * `acceptHandoff()`, `isGuestIdentityNotFound()` on `startScenario()`). Both are deterministic and
 * permanent for the current guest id: retrying with the same stale id repeats the same error
 * forever, since `createGuestIdentity()` reuses whatever it finds already cached. Every caller of
 * this self-heal is guaranteed a real fresh mint even if `backingStorage.remove()` itself fails
 * (e.g. "extension context invalidated", a storage write-rate limit) -- callers don't need to
 * remember to supply `fallbackStorage` themselves for the self-heal to actually work.
 *
 * Parameter named `backingStorage`, not `storage` -- see `createLocalStorageAdapter()`'s docstring
 * for why a bare `storage` identifier can't be used in a ce-kit source file bundled directly into
 * a Chrome-extension (WXT) build.
 */
export async function refreshGuestIdentity(
  client: PlatformApiClient,
  backingStorage: AsyncStorage,
  options?: RefreshGuestIdentityOptions,
): Promise<GuestIdentityResult> {
  const storageKey = options?.storageKey ?? DEFAULT_GUEST_STORAGE_KEY;
  let cleared = true;
  try {
    await backingStorage.remove(storageKey);
  } catch {
    cleared = false;
  }
  const targetStorage = cleared
    ? backingStorage
    : (options?.fallbackStorage ?? createInMemoryAsyncStorage());
  return client.createGuestIdentity({ storage: targetStorage, storageKey });
}
