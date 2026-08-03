import { abortedError, networkError, timeoutError } from "../errors";
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

  constructor(options: PlatformApiClientOptions) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl);
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch;
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
    const onExternalAbort = () => controller.abort();
    externalSignal?.addEventListener("abort", onExternalAbort);
    const timeoutHandle = setTimeout(() => controller.abort(), options.timeoutMs ?? this.timeoutMs);

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
        return { ok: false, error: externalSignal?.aborted ? abortedError() : timeoutError() };
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
}
