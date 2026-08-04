import type { AssertExactSchemaKeys } from "../api/driftAssertions";
import type { PlatformApiError } from "../api/errors";
import type { components } from "../api/generated/platformApi";
import type { AsyncStorage } from "../storage/asyncStorage";

export type GuestIdentity = {
  guestId: string;
};

export type GuestIdentityOptions = {
  storage: AsyncStorage;
  storageKey?: string;
};

export type GuestIdentityResult = { ok: true; value: GuestIdentity } | { ok: false; error: PlatformApiError };

export const DEFAULT_GUEST_STORAGE_KEY = "anytoolai.guest_id";

/** Extracts `guest_id` from the backend's GuestIdentityResponse payload, or null if malformed. */
export function parseGuestIdentityPayload(payload: unknown): string | null {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "guest_id" in payload &&
    typeof payload.guest_id === "string" &&
    payload.guest_id
  ) {
    return payload.guest_id;
  }
  return null;
}

// Compile-time drift check: fails typecheck if the backend's GuestIdentityResponse schema grows a
// field that parseGuestIdentityPayload() above doesn't know about.
const _guestIdentityResponseKeys = ["guest_id"] as const;
type _GuestIdentityResponseKeysCheck = AssertExactSchemaKeys<
  components["schemas"]["GuestIdentityResponse"],
  typeof _guestIdentityResponseKeys
>;
const _assertGuestIdentityResponseKeysMatchGenerated: _GuestIdentityResponseKeysCheck = true;
void _assertGuestIdentityResponseKeysMatchGenerated;
