export type GuestIdentity = {
  guestId: string;
};

export type GuestIdentityOptions = {
  apiBaseUrl?: string;
  storage?: Storage;
  storageKey?: string;
  fetchImpl?: typeof fetch;
};

const DEFAULT_STORAGE_KEY = "anytoolai.guest_id";

export async function createGuestIdentity(
  options: GuestIdentityOptions = {},
): Promise<GuestIdentity> {
  const storage = options.storage ?? _defaultStorage();
  const storageKey = options.storageKey ?? DEFAULT_STORAGE_KEY;
  const storedGuestId = storage?.getItem(storageKey);
  if (storedGuestId) {
    return { guestId: storedGuestId };
  }

  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  const response = await fetchImpl(`${options.apiBaseUrl ?? ""}/v1/identity/guest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error("Guest identity creation failed.");
  }

  const payload: unknown = await response.json();
  const guestId = _guestIdFromPayload(payload);
  storage?.setItem(storageKey, guestId);
  return { guestId };
}

function _defaultStorage(): Storage | undefined {
  return typeof globalThis.localStorage === "undefined"
    ? undefined
    : globalThis.localStorage;
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
