import type { AssertExactSchemaShape } from "../api/driftAssertions";
import type { components } from "../api/generated/platformApi";
import { isRecord } from "../api/parsing";
import type { HandoffCreated } from "./types";

/**
 * Validates and maps the backend's `HandoffCreateResponse` payload (snake_case) into the client's
 * `HandoffCreated` shape (camelCase). Returns null for anything that doesn't match, so callers
 * fall back to `invalid_response` instead of trusting arbitrary payload content.
 */
export function parseHandoffCreated(payload: unknown): HandoffCreated | null {
  if (!isRecord(payload)) {
    return null;
  }

  const {
    handoff_id: handoffId,
    handoff_token: handoffToken,
    status,
    expires_at: expiresAt,
  } = payload;

  if (
    typeof handoffId !== "string" ||
    typeof handoffToken !== "string" ||
    typeof status !== "string" ||
    typeof expiresAt !== "string"
  ) {
    return null;
  }

  return { handoffId, handoffToken, status, expiresAt };
}

// Compile-time drift check: fails typecheck if the backend's HandoffCreateResponse schema grows,
// loses, retypes, or changes the nullability/optionality of a field parseHandoffCreated() above
// doesn't know about.
type _HandoffCreateResponseShapeCheck = AssertExactSchemaShape<
  components["schemas"]["HandoffCreateResponse"],
  {
    expires_at: string;
    handoff_id: string;
    handoff_token: string;
    status: string;
  }
>;
const _assertHandoffCreateResponseShapeMatchesGenerated: _HandoffCreateResponseShapeCheck = true;
void _assertHandoffCreateResponseShapeMatchesGenerated;
