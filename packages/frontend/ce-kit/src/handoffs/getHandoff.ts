import { requestAndParse } from "../api/client";
import type { PlatformApiClient, PlatformApiRequestOptions, PlatformApiResult } from "../api/client";
import { parseHandoffPreview } from "./parseHandoffPreview";
import type { HandoffPreview } from "./types";

export type GetHandoffOptions = Pick<PlatformApiRequestOptions, "signal" | "timeoutMs">;

/**
 * `GET /v1/handoffs/{handoff_token}` -- fetches the current safe preview for a handoff token.
 * Never rejects on a terminal/expired status: the backend only raises `handoff_not_found` for an
 * unknown token, otherwise it always returns the preview with `status` reflecting the true
 * current state -- this is the authoritative way to render/refetch a terminal view.
 */
export async function getHandoff(
  client: PlatformApiClient,
  handoffToken: string,
  options?: GetHandoffOptions,
): Promise<PlatformApiResult<HandoffPreview>> {
  return requestAndParse(
    client,
    {
      method: "GET",
      path: `/v1/handoffs/${encodeURIComponent(handoffToken)}`,
      signal: options?.signal,
      timeoutMs: options?.timeoutMs,
    },
    parseHandoffPreview,
    "Handoff preview response was invalid.",
  );
}
