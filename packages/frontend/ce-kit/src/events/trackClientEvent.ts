import { requestAndParse } from "../api/client";
import type { PlatformApiClient, PlatformApiRequestOptions, PlatformApiResult } from "../api/client";
import { generateIdempotencyKey } from "../scenarios/idempotencyKey";
import { parseClientEventResponse } from "./parseClientEventResponse";
import type { ClientEventReceipt } from "./parseClientEventResponse";
import type { WebClientEventType } from "./webClientEventType";

/** The only scalar properties the backend allowlists -- see docs/architecture/event-taxonomy.md. */
export type ClientEventProperties = {
  mode?: string;
  fieldCount?: number;
  gapCategory?: string;
};

export type TrackClientEventRequest = {
  eventType: WebClientEventType;
  productId: string;
  frontendId: string;
  webSessionId: string;
  guestId?: string;
  userId?: string;
  scenarioSessionId?: string;
  properties?: ClientEventProperties;
};

export type TrackClientEventOptions = Pick<PlatformApiRequestOptions, "signal" | "timeoutMs">;

/**
 * Records one allowlisted `web.*` client event (ANY-17). Generates its own idempotent `event_id`
 * per call, so a caller must not retry a failed call with the same properties expecting a fresh
 * attempt -- retrying is safe (duplicate delivery is idempotent) but a genuinely new event needs a
 * new call.
 *
 * Never throws: like every other CE-kit helper, failure comes back as `{ ok: false, error }`, so a
 * caller can fire this without blocking or risking the product result on analytics delivery (the
 * platform contract explicitly allows client analytics to undercount).
 */
export async function trackClientEvent(
  client: PlatformApiClient,
  request: TrackClientEventRequest,
  options?: TrackClientEventOptions,
): Promise<PlatformApiResult<ClientEventReceipt>> {
  return requestAndParse(
    client,
    {
      method: "POST",
      path: "/v1/client-events",
      body: {
        event_id: generateIdempotencyKey(),
        event_type: request.eventType,
        product_id: request.productId,
        frontend_id: request.frontendId,
        web_session_id: request.webSessionId,
        guest_id: request.guestId,
        user_id: request.userId,
        scenario_session_id: request.scenarioSessionId,
        properties: toWireProperties(request.properties),
      },
      signal: options?.signal,
      timeoutMs: options?.timeoutMs,
    },
    parseClientEventResponse,
    "Client event response was invalid.",
  );
}

function toWireProperties(
  properties: ClientEventProperties | undefined,
): Record<string, string | number> | undefined {
  if (properties === undefined) {
    return undefined;
  }
  const wire: Record<string, string | number> = {};
  if (properties.mode !== undefined) {
    wire.mode = properties.mode;
  }
  // Number.isInteger() (not just isFinite()) -- the backend's field_count is a Python `int`, so a
  // finite non-integer like 2.5 would fail isinstance(value, int) there and fail the whole event
  // with the generic client_event_property_invalid, same as NaN/Infinity would. isInteger()
  // already excludes NaN/Infinity too, so this is the one check that covers both.
  if (properties.fieldCount !== undefined && Number.isInteger(properties.fieldCount)) {
    wire.field_count = properties.fieldCount;
  }
  if (properties.gapCategory !== undefined) {
    wire.gap_category = properties.gapCategory;
  }
  return wire;
}
