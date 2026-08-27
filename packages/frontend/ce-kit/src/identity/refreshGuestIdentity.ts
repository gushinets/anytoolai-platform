import type { PlatformApiClient } from "../api/client";
import type { AsyncStorage } from "../storage/asyncStorage";
import { DEFAULT_GUEST_STORAGE_KEY, type GuestIdentityResult } from "./guestIdentity";

export type RefreshGuestIdentityOptions = {
  storageKey?: string;
  /** Used for this mint only if clearing `backingStorage` itself fails -- a failed removal can't
   * be trusted to have actually forgotten the stale id, so this avoids risking
   * `createGuestIdentity()` reading the same stale value straight back out of it. */
  fallbackStorage?: AsyncStorage;
};

/**
 * Clears whatever guest id is currently persisted in `backingStorage` and mints a fresh one -- the
 * self-heal for a guest id the backend no longer recognizes (`isHandoffGuestIdentityInvalid()` on
 * `acceptHandoff()`, `isGuestIdentityNotFound()` on `startScenario()`). Both are deterministic and
 * permanent for the current guest id: retrying with the same stale id repeats the same error
 * forever, since `createGuestIdentity()` reuses whatever it finds already cached.
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
  const targetStorage = cleared ? backingStorage : (options?.fallbackStorage ?? backingStorage);
  return client.createGuestIdentity({ storage: targetStorage, storageKey });
}
