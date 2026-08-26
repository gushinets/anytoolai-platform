import { requestAndParse } from "../api/client";
import type { PlatformApiClient, PlatformApiRequestOptions, PlatformApiResult } from "../api/client";
import { parseHandoffPreview } from "./parseHandoffPreview";
import type { AcceptHandoffRequest, HandoffPreview } from "./types";

export type AcceptHandoffOptions = Pick<PlatformApiRequestOptions, "signal" | "timeoutMs">;

/**
 * `POST /v1/handoffs/{handoff_token}/accept` -- accepts the handoff and returns its updated
 * preview. Can raise `handoff_expired` (410), the `handoff_not_actionable` family (409, already
 * accepted/declined/failed -- see `isHandoffNotActionable()`), `quota_exhausted` (429, see
 * `isQuotaExhausted()`), `handoff_source_invalid` (500, the source session vanished between
 * creation and acceptance -- see `isHandoffSourceInvalid()`), or `handoff_acceptance_failed` (500,
 * see `isHandoffAcceptanceFailed()`).
 * `request` is optional -- an omitted `guestId`/`sourceFrontendInstanceId` is dropped from the
 * body, matching the backend's own optional `HandoffAcceptRequest` fields.
 */
export async function acceptHandoff(
  client: PlatformApiClient,
  handoffToken: string,
  request?: AcceptHandoffRequest,
  options?: AcceptHandoffOptions,
): Promise<PlatformApiResult<HandoffPreview>> {
  return requestAndParse(
    client,
    {
      method: "POST",
      path: `/v1/handoffs/${encodeURIComponent(handoffToken)}/accept`,
      body: {
        guest_id: request?.guestId,
        source_frontend_instance_id: request?.sourceFrontendInstanceId,
      },
      signal: options?.signal,
      timeoutMs: options?.timeoutMs,
    },
    parseHandoffPreview,
    "Handoff acceptance response was invalid.",
  );
}
