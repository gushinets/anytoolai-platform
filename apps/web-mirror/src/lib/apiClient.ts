import { PlatformApiClient } from "@anytoolai/ce-kit";

/**
 * Same-origin base URL: `next.config.ts` rewrites `/v1/:path*` to platform-api, whose port
 * varies per checkout (see scripts/agent/runner.py's dev-up port-offset logic). Falls back to
 * `http://localhost` outside the browser (e.g. a future server-rendered caller) where there is
 * no `window.location` to read.
 */
export function createPlatformApiClient(): PlatformApiClient {
  return new PlatformApiClient({
    baseUrl: typeof window !== "undefined" ? window.location.origin : "http://localhost",
  });
}

let browserClient: PlatformApiClient | undefined;

/**
 * The one client for this page load. Everything that must outlive a component remount -- the
 * single-flight guest identity and, through `getClientStorage(client)`, the guest id and
 * `web_session_id` -- hangs off the client, so its lifetime must not be tied to a component:
 * Client Update Writer's mode switch remounts `ProductRunPage`, and a page-level `useMemo` only
 * lasts as long as that page's own mount. Owned by the module instead, so any remount or future
 * client-side navigation keeps it, and a full page load (the only way to move between products
 * today -- nothing in the app links or routes between them) starts fresh.
 *
 * Not cached outside the browser: on the server there is no origin to build a real client from.
 */
export function getPlatformApiClient(): PlatformApiClient {
  if (typeof window === "undefined") {
    return createPlatformApiClient();
  }
  browserClient ??= createPlatformApiClient();
  return browserClient;
}
