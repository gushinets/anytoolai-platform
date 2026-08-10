import { requestAndParse } from "../api/client";
import type { PlatformApiClient, PlatformApiRequestOptions, PlatformApiResult } from "../api/client";
import { parseResultArtifact } from "./parseResultArtifact";
import type { ResultArtifact } from "./types";

export type GetResultOptions = Pick<PlatformApiRequestOptions, "signal" | "timeoutMs">;

/**
 * Typed `GET /v1/results/{result_artifact_id}` read of a completed, frontend-safe normalized
 * workflow result -- the `resultArtifactId` a terminal `pollScenarioSession()` /
 * `getScenarioSession()` snapshot surfaces. Callers never construct this URL themselves.
 */
export async function getResult(
  client: PlatformApiClient,
  resultArtifactId: string,
  options?: GetResultOptions,
): Promise<PlatformApiResult<ResultArtifact>> {
  return requestAndParse(
    client,
    {
      method: "GET",
      path: `/v1/results/${encodeURIComponent(resultArtifactId)}`,
      signal: options?.signal,
      timeoutMs: options?.timeoutMs,
    },
    parseResultArtifact,
    "Result artifact response was invalid.",
  );
}
