import type { PlatformApiError } from "../errors";
import type { PlatformApiMethod } from "./http";

export type PlatformApiRetryPolicy = {
  /** Total attempts including the first, e.g. 3 = 1 initial try + up to 2 retries. */
  attempts: number;
  delayMs?: number;
};

/** Safe HTTP methods are the only ones the client will ever retry automatically. */
const SAFE_METHODS: ReadonlySet<PlatformApiMethod> = new Set(["GET"]);

/** Throws synchronously (before any network call) if a retry policy is set on an unsafe method. */
export function assertRetryAllowed(
  method: PlatformApiMethod,
  path: string,
  retry: PlatformApiRetryPolicy | undefined,
): void {
  if (retry && !SAFE_METHODS.has(method)) {
    throw new Error(
      `PlatformApiClient: retry is only supported for safe GET requests, got ${method} ${path}.`,
    );
  }
}

export function isRetryable(error: PlatformApiError): boolean {
  return error.type === "network_error" || error.type === "timeout";
}

/**
 * Whether a failed request leaves it unknown if the backend already acted on it: a lost response, a
 * timeout or a 5xx. Repeating it is only safe for a request that carries an Idempotency-Key (a
 * scenario start); a definite 4xx, an aborted request and a response the client could not parse
 * (deterministic) are not ambiguous.
 */
export function isAmbiguousFailure(error: PlatformApiError): boolean {
  return isRetryable(error) || (error.type === "backend_error" && error.status >= 500);
}

/**
 * Resolves after `ms`, or immediately if `signal` aborts first -- the caller distinguishes the two
 * outcomes via `signal.aborted` after this settles. Always removes its listener/timer so an
 * already-settled retry loop can't leak either.
 */
export function delay(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const onAbort = () => {
      clearTimeout(timeoutHandle);
      resolve();
    };
    const timeoutHandle = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}
