import { vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";

export type RoutedFetchClient = {
  client: PlatformApiClient;
  calls: Array<{ key: string; init: RequestInit }>;
};

function routeKey(url: string, method: string): string {
  return `${method} ${new URL(url).pathname}`;
}

/**
 * Dispatches a fake `fetch` by (method, path) instead of call order, so a caller whose component
 * fires more than one request concurrently (e.g. via `Promise.all`) isn't fragile to their actual
 * interleaving. Each route is a FIFO queue of responses, so the same endpoint (e.g. a preview GET
 * hit again on refetch) can return a different response on each call.
 */
export function makeRoutedFetchClient(
  baseUrl: string,
  routes: Record<string, Array<Response | (() => Response)>>,
): RoutedFetchClient {
  const queues = new Map(Object.entries(routes).map(([key, responses]) => [key, [...responses]]));
  const calls: Array<{ key: string; init: RequestInit }> = [];
  const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
    const key = routeKey(url, init.method ?? "GET");
    calls.push({ key, init });
    const queue = queues.get(key);
    if (!queue || queue.length === 0) {
      throw new Error(`No mock response queued for ${key}`);
    }
    const next = queue.shift();
    return typeof next === "function" ? next() : (next as Response);
  });
  return {
    client: new PlatformApiClient({ baseUrl, fetchImpl: fetchImpl as unknown as typeof fetch }),
    calls,
  };
}
