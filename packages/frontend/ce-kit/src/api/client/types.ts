import type { PlatformApiError } from "../errors";
import type { PlatformApiMethod } from "./http";
import type { PlatformApiRetryPolicy } from "./retry";

export type PlatformApiResult<T> =
  | { ok: true; value: T }
  | { ok: false; error: PlatformApiError };

export type PlatformApiRequestOptions = {
  method?: PlatformApiMethod;
  path: string;
  body?: unknown;
  headers?: Record<string, string>;
  requestId?: string;
  /** Caller-supplied cancellation; independent of the client's own timeout. */
  signal?: AbortSignal;
  timeoutMs?: number;
  /** Only honored for safe (GET) requests -- see retry.ts's assertRetryAllowed(). */
  retry?: PlatformApiRetryPolicy;
};

export type PlatformApiClientOptions = {
  baseUrl: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
  defaultHeaders?: Record<string, string>;
};
