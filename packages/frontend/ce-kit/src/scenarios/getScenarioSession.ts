import { requestAndParse } from "../api/client";
import type { PlatformApiClient, PlatformApiRequestOptions, PlatformApiResult } from "../api/client";
import { parseScenarioSession } from "./parseScenarioSessionSnapshot";
import type { ScenarioSession } from "./types";

export type GetScenarioSessionOptions = Pick<PlatformApiRequestOptions, "signal" | "timeoutMs">;

export async function getScenarioSession(
  client: PlatformApiClient,
  scenarioSessionId: string,
  options?: GetScenarioSessionOptions,
): Promise<PlatformApiResult<ScenarioSession>> {
  return requestAndParse(
    client,
    {
      method: "GET",
      path: `/v1/scenario-sessions/${encodeURIComponent(scenarioSessionId)}`,
      signal: options?.signal,
      timeoutMs: options?.timeoutMs,
    },
    parseScenarioSession,
    "Scenario session response was invalid.",
  );
}
