import { requestAndParse } from "../api/client";
import type { PlatformApiClient, PlatformApiRequestOptions, PlatformApiResult } from "../api/client";
import { parseHandoffPreview } from "./parseHandoffPreview";
import type { HandoffPreview } from "./types";

export type DeclineHandoffOptions = Pick<PlatformApiRequestOptions, "signal" | "timeoutMs">;

/**
 * `POST /v1/handoffs/{handoff_token}/decline` -- declines the handoff and returns its updated
 * preview. No request body. Can raise `handoff_expired` (410) or the `handoff_not_actionable`
 * family (409, see `isHandoffNotActionable()`).
 */
export async function declineHandoff(
  client: PlatformApiClient,
  handoffToken: string,
  options?: DeclineHandoffOptions,
): Promise<PlatformApiResult<HandoffPreview>> {
  return requestAndParse(
    client,
    {
      method: "POST",
      path: `/v1/handoffs/${encodeURIComponent(handoffToken)}/decline`,
      signal: options?.signal,
      timeoutMs: options?.timeoutMs,
    },
    parseHandoffPreview,
    "Handoff decline response was invalid.",
  );
}
