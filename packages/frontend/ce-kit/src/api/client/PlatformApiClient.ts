import {
  DEFAULT_GUEST_STORAGE_KEY,
  parseGuestIdentityPayload,
  type GuestIdentityOptions,
  type GuestIdentityResult,
} from "../../identity/guestIdentity";
import { abortedError, invalidResponseError, networkError, timeoutError } from "../errors";
import { buildHeaders } from "./headers";
import type { PlatformApiMethod } from "./http";
import { toResult } from "./response";
import { assertRetryAllowed, delay, isRetryable } from "./retry";
import type { PlatformApiClientOptions, PlatformApiRequestOptions, PlatformApiResult } from "./types";
import { joinUrl, normalizeBaseUrl } from "./url";

const DEFAULT_TIMEOUT_MS = 10_000;

export class PlatformApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;
  private readonly defaultHeaders: Record<string, string>;
  /** Single-flight guard for createGuestIdentity(), scoped to this client instance only. */
  private inFlightGuestIdentity: Promise<GuestIdentityResult> | null = null;
  /**
   * Count of createGuestIdentity() calls currently in flight (from method entry through their
   * own storage lookup and persistence, not just the shared backend request). `inFlightGuestIdentity`
   * is only cleared once this reaches zero, so a caller whose own `storage.get()` is still pending
   * when another caller's request already finished still joins that same request instead of
   * starting a second one.
   */
  private activeGuestIdentityCalls = 0;

  constructor(options: PlatformApiClientOptions) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl);
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.defaultHeaders = options.defaultHeaders ?? {};
  }

  async request<T>(options: PlatformApiRequestOptions): Promise<PlatformApiResult<T>> {
    const method = options.method ?? "GET";
    assertRetryAllowed(method, options.path, options.retry);

    const attempts = options.retry ? Math.max(1, options.retry.attempts) : 1;
    let result: PlatformApiResult<T> = await this.performOnce<T>(method, options);
    for (let attempt = 2; attempt <= attempts && !result.ok && isRetryable(result.error); attempt += 1) {
      if (options.retry?.delayMs) {
        await delay(options.retry.delayMs, options.signal);
      }
      // Checked unconditionally, not just after a delay -- with `delayMs` unset or `0` the loop
      // would otherwise call `performOnce()` (and thus `fetchImpl`) again immediately after the
      // caller already cancelled, even though no wait ever happened to observe the signal.
      if (options.signal?.aborted) {
        return { ok: false, error: abortedError() };
      }
      result = await this.performOnce<T>(method, options);
    }
    return result;
  }

  private async performOnce<T>(
    method: PlatformApiMethod,
    options: PlatformApiRequestOptions,
  ): Promise<PlatformApiResult<T>> {
    const url = joinUrl(this.baseUrl, options.path);
    const headers = buildHeaders(
      this.defaultHeaders,
      options.headers,
      options.requestId,
      options.body !== undefined,
    );
    const controller = new AbortController();
    const externalSignal = options.signal;
    // Recorded at the moment each trigger actually aborts, not re-derived from signal state
    // after the fetch rejection settles -- otherwise a timeout that fires first can be
    // misreported as `aborted` if the caller's signal also aborts before the rejection lands.
    let abortReason: "timeout" | "external" | null = null;
    const onExternalAbort = () => {
      abortReason ??= "external";
      controller.abort();
    };
    if (externalSignal?.aborted) {
      onExternalAbort();
    } else {
      externalSignal?.addEventListener("abort", onExternalAbort);
    }
    const timeoutHandle = setTimeout(() => {
      abortReason ??= "timeout";
      controller.abort();
    }, options.timeoutMs ?? this.timeoutMs);

    try {
      const response = await this.fetchImpl(url, {
        method,
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: controller.signal,
      });
      return await toResult<T>(response);
    } catch (cause) {
      if (controller.signal.aborted) {
        return { ok: false, error: abortReason === "timeout" ? timeoutError() : abortedError() };
      }
      // `cause` may hold sensitive detail (URLs, headers, internal exception text) -- never surface
      // it in the public result. Raw detail is dropped here; wire up a private diagnostics sink if
      // that ever needs to be observable.
      void cause;
      return {
        ok: false,
        error: networkError(),
      };
    } finally {
      clearTimeout(timeoutHandle);
      externalSignal?.removeEventListener("abort", onExternalAbort);
    }
  }

  /**
   * Reuses a persisted guest id if present, otherwise requests one from the backend and persists
   * it. Concurrent calls on this client instance are single-flight -- at most one backend request
   * is made no matter how many callers ask at once, which `storageKey` each passes, or how long
   * any individual caller's own `storage.get()` takes to resolve (coordination is scoped to the
   * whole call, from entry through persistence, not just around the backend request itself, so a
   * slow storage lookup can't miss a request that started and finished while it was still
   * pending). Every successful caller persists the (shared) result to its own
   * `storage`/`storageKey`, not just whichever call happened to trigger the backend request.
   */
  async createGuestIdentity(options: GuestIdentityOptions): Promise<GuestIdentityResult> {
    this.activeGuestIdentityCalls += 1;
    try {
      const storageKey = options.storageKey ?? DEFAULT_GUEST_STORAGE_KEY;
      let storedGuestId: string | undefined;
      let storageReadFailed = false;
      try {
        storedGuestId = await options.storage.get(storageKey);
      } catch {
        // A failed cache read is treated as a cache miss -- it must not surface as an arbitrary
        // exception from createGuestIdentity(), and the backend fallback below still produces a
        // valid GuestIdentityResult.
        storageReadFailed = true;
      }
      if (storedGuestId) {
        return { ok: true, value: { guestId: storedGuestId } };
      }

      const result = await this.shareGuestIdentityRequest();
      // Skip persisting when this caller's own read failed: a concurrent caller under the same
      // `storageKey` may have read a genuinely cached id successfully (and already returned it
      // above, without joining this shared request) while this call's read merely errored --
      // blindly writing here would clobber that still-valid cached id with a second, different
      // guest id from the same backend response, orphaning the one the other caller already used.
      if (result.ok && !storageReadFailed) {
        try {
          await options.storage.set(storageKey, result.value.guestId);
        } catch {
          // The backend already created this identity; a storage failure must not discard it --
          // that would orphan it on the backend and cause the next call to create a duplicate.
          // Persistence is best-effort here, the identity itself is still valid.
        }
      }
      return result;
    } finally {
      this.activeGuestIdentityCalls -= 1;
      if (this.activeGuestIdentityCalls === 0) {
        this.inFlightGuestIdentity = null;
      }
    }
  }

  private shareGuestIdentityRequest(): Promise<GuestIdentityResult> {
    if (!this.inFlightGuestIdentity) {
      this.inFlightGuestIdentity = this.requestGuestIdentity();
    }
    return this.inFlightGuestIdentity;
  }

  private async requestGuestIdentity(): Promise<GuestIdentityResult> {
    const result = await this.request<unknown>({ method: "POST", path: "/v1/identity/guest" });
    if (!result.ok) {
      return result;
    }

    const guestId = parseGuestIdentityPayload(result.value);
    if (guestId === null) {
      return {
        ok: false,
        error: invalidResponseError(result.status, "Guest identity response was invalid."),
      };
    }

    return { ok: true, value: { guestId } };
  }
}
