import { requestAndParse } from "../api/client";
import type { PlatformApiClient, PlatformApiRequestOptions, PlatformApiResult } from "../api/client";
import { generateIdempotencyKey } from "./idempotencyKey";
import { parseScenarioSessionSnapshot } from "./parseScenarioSessionSnapshot";
import type { ScenarioSessionSnapshot, ScenarioStartRequest } from "./types";

/** Independent of the client's own timeout; cancels this attempt only. */
export type PreparedScenarioStartExecuteOptions = Pick<
  PlatformApiRequestOptions,
  "signal" | "timeoutMs"
>;

/**
 * An opaque, retryable handle for one logical scenario-start submission (ANY-150).
 *
 * `prepareScenarioStart()` generates one `Idempotency-Key` up front; every `execute()` call on
 * the same handle -- including explicit retries of an ambiguous failure -- reuses that key, so
 * the backend can collapse duplicate submits into the original session/job instead of consuming
 * quota twice. Calling code never sees or manages the key or its header directly. To submit a
 * genuinely new request, call `prepareScenarioStart()` again to get a new key.
 */
export type PreparedScenarioStart = {
  execute(
    client: PlatformApiClient,
    options?: PreparedScenarioStartExecuteOptions,
  ): Promise<PlatformApiResult<ScenarioSessionSnapshot>>;
};

export function prepareScenarioStart(request: ScenarioStartRequest): PreparedScenarioStart {
  const idempotencyKey = generateIdempotencyKey();

  return {
    execute(client, options) {
      return requestAndParse(
        client,
        {
          method: "POST",
          path: `/v1/products/${encodeURIComponent(request.productId)}/scenarios/${encodeURIComponent(request.scenarioId)}/start`,
          body: {
            frontend_id: request.frontendId,
            input: request.input,
            guest_id: request.guestId ?? null,
            user_id: request.userId ?? null,
            source_frontend_instance_id: request.sourceFrontendInstanceId ?? null,
          },
          headers: { "Idempotency-Key": idempotencyKey },
          signal: options?.signal,
          timeoutMs: options?.timeoutMs,
        },
        parseScenarioSessionSnapshot,
        "Scenario start response was invalid.",
      );
    },
  };
}
