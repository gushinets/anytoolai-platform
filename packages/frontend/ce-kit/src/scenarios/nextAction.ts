import { requestAndParse } from "../api/client";
import type { PlatformApiClient, PlatformApiResult } from "../api/client";
import { parseScenarioSession } from "./parseScenarioSessionSnapshot";
import type { ScenarioSession } from "./types";

export type NextActionRequest = {
  scenarioSessionId: string;
  nextActionId: string;
  /** The checkpoint this action is being taken against; the backend is authoritative on staleness. */
  checkpointId: string;
};

export type NextActionOptions = {
  signal?: AbortSignal;
  timeoutMs?: number;
};

/**
 * Sends the current checkpoint for a next-action click and treats the backend's validation as
 * authoritative -- a stale/disallowed checkpoint comes back as `409`, not a client-side check.
 */
export async function nextAction(
  client: PlatformApiClient,
  request: NextActionRequest,
  options?: NextActionOptions,
): Promise<PlatformApiResult<ScenarioSession>> {
  return requestAndParse(
    client,
    {
      method: "POST",
      path: `/v1/scenario-sessions/${encodeURIComponent(request.scenarioSessionId)}/next-actions/${encodeURIComponent(request.nextActionId)}`,
      body: { checkpoint_id: request.checkpointId },
      signal: options?.signal,
      timeoutMs: options?.timeoutMs,
    },
    parseScenarioSession,
    "Scenario session response was invalid.",
  );
}
