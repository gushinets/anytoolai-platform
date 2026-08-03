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

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
