import { requestAndParse } from "../api/client";
import type { PlatformApiClient, PlatformApiRequestOptions, PlatformApiResult } from "../api/client";
import { parseHandoffCreated } from "./parseHandoffCreated";
import type { CreateHandoffRequest, HandoffCreated } from "./types";

export type CreateHandoffOptions = Pick<PlatformApiRequestOptions, "signal" | "timeoutMs">;

/**
 * `POST /v1/handoffs` -- mints a fresh handoff token for the given definition and source. No
 * `Idempotency-Key` handling: unlike `prepareScenarioStart()`, the backend has no idempotency-key
 * logic for this endpoint.
 */
export async function createHandoff(
  client: PlatformApiClient,
  request: CreateHandoffRequest,
  options?: CreateHandoffOptions,
): Promise<PlatformApiResult<HandoffCreated>> {
  return requestAndParse(
    client,
    {
      method: "POST",
      path: "/v1/handoffs",
      body: {
        handoff_definition_id: request.handoffDefinitionId,
        source_scenario_session_id: request.sourceScenarioSessionId,
        source_artifact_id: request.sourceArtifactId,
      },
      signal: options?.signal,
      timeoutMs: options?.timeoutMs,
    },
    parseHandoffCreated,
    "Handoff creation response was invalid.",
  );
}
