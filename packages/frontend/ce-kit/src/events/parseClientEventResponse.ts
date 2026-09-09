import type { AssertExactSchemaShape } from "../api/driftAssertions";
import type { components } from "../api/generated/platformApi";
import { isRecord } from "../api/parsing";

export type ClientEventReceipt = {
  eventId: string;
  eventType: string;
};

/** Validates the backend's `ClientEventResponse` payload, or null if malformed. */
export function parseClientEventResponse(payload: unknown): ClientEventReceipt | null {
  if (!isRecord(payload)) {
    return null;
  }

  const { event_id: eventId, event_type: eventType } = payload;
  if (typeof eventId !== "string" || typeof eventType !== "string") {
    return null;
  }

  return { eventId, eventType };
}

// Compile-time drift check: fails typecheck if the backend's ClientEventResponse schema grows,
// loses, retypes, or changes the nullability of a field parseClientEventResponse() doesn't know
// about.
type _ClientEventResponseShapeCheck = AssertExactSchemaShape<
  components["schemas"]["ClientEventResponse"],
  { event_id: string; event_type: string }
>;
const _assertClientEventResponseShapeMatchesGenerated: _ClientEventResponseShapeCheck = true;
void _assertClientEventResponseShapeMatchesGenerated;
