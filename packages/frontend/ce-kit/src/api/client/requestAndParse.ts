import { invalidResponseError } from "../errors";
import type { PlatformApiClient } from "./PlatformApiClient";
import type { PlatformApiRequestOptions, PlatformApiResult } from "./types";

/**
 * The one shared shape behind every typed CE-kit helper: request -> if not ok, pass the error
 * through unchanged -> parse the payload -> fall back to `invalid_response` if it doesn't match
 * -> wrap the parsed value back into a `PlatformApiResult`. Centralizing it here means a change to
 * this flow (e.g. how `invalid_response` is built, or adding logging) happens once instead of at
 * every call site.
 */
export async function requestAndParse<T>(
  client: PlatformApiClient,
  requestOptions: PlatformApiRequestOptions,
  parse: (payload: unknown) => T | null,
  invalidResponseMessage: string,
): Promise<PlatformApiResult<T>> {
  const result = await client.request<unknown>(requestOptions);
  if (!result.ok) {
    return result;
  }

  const value = parse(result.value);
  if (value === null) {
    return { ok: false, error: invalidResponseError(result.status, invalidResponseMessage) };
  }

  return { ok: true, value, status: result.status };
}