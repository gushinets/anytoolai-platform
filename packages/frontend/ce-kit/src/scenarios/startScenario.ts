import type { PlatformApiClient, PlatformApiResult } from "../api/client";
import { prepareScenarioStart } from "./prepareScenarioStart";
import type { ScenarioSessionSnapshot, ScenarioStartRequest } from "./types";

/**
 * Convenience one-shot start: prepares a single `Idempotency-Key`-bound operation (ANY-150) and
 * executes it immediately. Callers that need to retry an ambiguous failure with the same key --
 * rather than risk a new submission double-charging quota -- must use `prepareScenarioStart()`
 * directly and call `.execute()` again on the same handle instead of calling `startScenario()`
 * a second time.
 */
export async function startScenario(
  client: PlatformApiClient,
  request: ScenarioStartRequest,
): Promise<PlatformApiResult<ScenarioSessionSnapshot>> {
  return prepareScenarioStart(request).execute(client);
}
