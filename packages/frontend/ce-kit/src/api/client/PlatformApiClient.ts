import {
  DEFAULT_GUEST_STORAGE_KEY,
  parseGuestIdentityPayload,
  type GuestIdentityOptions,
  type GuestIdentityResult,
} from "../../identity/guestIdentity";
import type { AsyncStorage } from "../../storage/asyncStorage";
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
        await delay(options.retry.delayMs);
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
      return {
        ok: false,
        error: networkError(cause instanceof Error ? cause.message : undefined),
      };
    } finally {
      clearTimeout(timeoutHandle);
      externalSignal?.removeEventListener("abort", onExternalAbort);
    }
  }

  /**
   * Reuses a persisted guest id if present, otherwise requests one from the backend and persists
   * it. Concurrent calls on this client instance are single-flight -- at most one backend request
   * is made no matter how many callers ask at once or which `storageKey` each passes; only the
   * call that actually performs the request persists to its own `storageKey`.
   */
  async createGuestIdentity(options: GuestIdentityOptions): Promise<GuestIdentityResult> {
    const storageKey = options.storageKey ?? DEFAULT_GUEST_STORAGE_KEY;
    const storedGuestId = await options.storage.get(storageKey);
    if (storedGuestId) {
      return { ok: true, value: { guestId: storedGuestId } };
    }

    if (this.inFlightGuestIdentity) {
      return this.inFlightGuestIdentity;
    }

    const request = this.requestGuestIdentity(options.storage, storageKey).finally(() => {
      this.inFlightGuestIdentity = null;
    });
    this.inFlightGuestIdentity = request;
    return request;
  }

  private async requestGuestIdentity(
    storage: AsyncStorage,
    storageKey: string,
  ): Promise<GuestIdentityResult> {
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

    try {
      await storage.set(storageKey, guestId);
    } catch {
      // The backend already created this identity; a storage failure must not discard it --
      // that would orphan it on the backend and cause the next call to create a duplicate.
      // Persistence is best-effort here, the identity itself is still valid.
    }
    return { ok: true, value: { guestId } };
  }
}
