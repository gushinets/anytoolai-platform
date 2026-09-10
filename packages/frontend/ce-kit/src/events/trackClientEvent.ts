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
  /**
   * Reuse the same id across retries of one logical event, so duplicate delivery dedupes
   * server-side instead of creating a second row -- generate it once with
   * `generateIdempotencyKey()` (exported from this package) and pass the same value to every
   * retry of that call. Omit to mint a fresh one for this call only, which is safe as long as
   * the caller never itself retries with a "new" id for what is really the same logical event.
   */
  eventId?: string;
};

export type TrackClientEventOptions = Pick<PlatformApiRequestOptions, "signal" | "timeoutMs">;

/**
 * Records one allowlisted `web.*` client event (ANY-17). Mints a fresh idempotent `event_id` per
 * call unless the caller supplies one via `request.eventId` -- a caller that itself retries (e.g.
 * after a timeout where the first attempt may have actually committed) must pass the same
 * `eventId` on every retry of one logical event, or duplicate delivery will create a second row
 * instead of deduping.
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
        event_id: request.eventId ?? generateIdempotencyKey(),
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
