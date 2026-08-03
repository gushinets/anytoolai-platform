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

/** Keyed by client instance so concurrent calls sharing a client share one in-flight request. */
const inFlightRequests = new WeakMap<PlatformApiClient, Promise<GuestIdentity>>();

export async function createGuestIdentity(
  options: GuestIdentityOptions,
): Promise<GuestIdentity> {
  const { client, storage } = options;
  const storageKey = options.storageKey ?? DEFAULT_STORAGE_KEY;

  const storedGuestId = await storage.get(storageKey);
  if (storedGuestId) {
    return { guestId: storedGuestId };
  }

  const inFlight = inFlightRequests.get(client);
  if (inFlight) {
    return inFlight;
  }

  const request = _requestGuestIdentity(client, storage, storageKey).finally(() => {
    inFlightRequests.delete(client);
  });
  inFlightRequests.set(client, request);
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
    throw new Error(`Guest identity creation failed: ${result.error.type}`);
  }

  const guestId = _guestIdFromPayload(result.value);
  await storage.set(storageKey, guestId);
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
