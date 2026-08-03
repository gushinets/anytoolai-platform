import { backendError, invalidResponseError, parseBackendErrorEnvelope } from "../errors";
import type { PlatformApiResult } from "./types";

const INVALID_JSON = Symbol("invalid_json");

export async function toResult<T>(response: Response): Promise<PlatformApiResult<T>> {
  const payload = await safeParseJson(response);

  if (!response.ok) {
    const detail = payload === INVALID_JSON || payload === undefined
      ? null
      : parseBackendErrorEnvelope(payload);
    return detail
      ? { ok: false, error: backendError(response.status, detail) }
      : { ok: false, error: invalidResponseError(response.status) };
  }

  if (payload === INVALID_JSON) {
    return {
      ok: false,
      error: invalidResponseError(response.status, "Response body was not valid JSON."),
    };
  }

  return { ok: true, value: payload as T };
}

async function safeParseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text.length === 0) {
    return undefined;
  }
  try {
    return JSON.parse(text);
  } catch {
    return INVALID_JSON;
  }
}
