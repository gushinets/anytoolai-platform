import type { PlatformApiClient, PlatformApiResult } from "../api/client";
import { invalidResponseError } from "../api/errors";
import { parseRuntimeConfig } from "./parseRuntimeConfig";
import type { RuntimeConfig } from "./types";

export async function getRuntimeConfig(
  client: PlatformApiClient,
  productId: string,
): Promise<PlatformApiResult<RuntimeConfig>> {
  const result = await client.request<unknown>({
    method: "GET",
    path: `/v1/products/${encodeURIComponent(productId)}/runtime-config`,
  });
  if (!result.ok) {
    return result;
  }

  const runtimeConfig = parseRuntimeConfig(result.value);
  if (!runtimeConfig) {
    return {
      ok: false,
      error: invalidResponseError(result.status, "Runtime config response was invalid."),
    };
  }

  return { ok: true, value: runtimeConfig, status: result.status };
}
