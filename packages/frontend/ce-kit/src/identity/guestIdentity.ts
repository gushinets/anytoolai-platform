import type { PlatformApiClient } from "../api/client";
import type { AsyncStorage } from "../storage/asyncStorage";

export type GuestIdentity = {
  guestId: string;
};

export type GuestIdentityOptions = {
  client: PlatformApiClient;
  storage: AsyncStorage;
  storageKey?: string;
};

const DEFAULT_STORAGE_KEY = "anytoolai.guest_id";

/**
 * Keyed by client instance, then by storageKey, so concurrent calls only collapse into one
 * in-flight request when they'd also persist to the same storage slot.
 */
const inFlightRequestsByClient = new WeakMap<
  PlatformApiClient,
  Map<string, Promise<GuestIdentity>>
>();

export async function createGuestIdentity(
  options: GuestIdentityOptions,
): Promise<GuestIdentity> {
  const { client, storage } = options;
  const storageKey = options.storageKey ?? DEFAULT_STORAGE_KEY;

  const storedGuestId = await storage.get(storageKey);
  if (storedGuestId) {
    return { guestId: storedGuestId };
  }

  const inFlightByKey = inFlightRequestsByClient.get(client);
  const inFlight = inFlightByKey?.get(storageKey);
  if (inFlight) {
    return inFlight;
  }

  const request = _requestGuestIdentity(client, storage, storageKey).finally(() => {
    inFlightRequestsByClient.get(client)?.delete(storageKey);
  });
  if (inFlightByKey) {
    inFlightByKey.set(storageKey, request);
  } else {
    inFlightRequestsByClient.set(client, new Map([[storageKey, request]]));
  }
  return request;
}

async function _requestGuestIdentity(
  client: PlatformApiClient,
  storage: AsyncStorage,
  storageKey: string,
): Promise<GuestIdentity> {
  const result = await client.request<unknown>({
    method: "POST",
    path: "/v1/identity/guest",
  });
  if (!result.ok) {
    throw new Error(`Guest identity creation failed: ${result.error.type}`, { cause: result.error });
  }

  const guestId = _guestIdFromPayload(result.value);
  try {
    await storage.set(storageKey, guestId);
  } catch {
    // The backend already created this identity; a storage failure must not discard it --
    // that would orphan it on the backend and cause the next call to create a duplicate.
    // Persistence is best-effort here, the identity itself is still valid.
  }
  return { guestId };
}

function _guestIdFromPayload(payload: unknown): string {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "guest_id" in payload &&
    typeof payload.guest_id === "string" &&
    payload.guest_id
  ) {
    return payload.guest_id;
  }
  throw new Error("Guest identity response was invalid.");
}
