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
