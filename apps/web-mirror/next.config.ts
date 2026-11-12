import type { NextConfig } from "next";
import { DEFAULT_PORTAL_CONSUMER_ID } from "./src/lib/portalConsumer";

// HandoffConsent.tsx/HandoffPage build their PlatformApiClient with `window.location.origin` and
// call paths like `/v1/handoffs/{token}` -- this rewrite is what makes those same-origin requests
// actually reach platform-api, whose port varies per checkout (see scripts/agent/runner.py's
// dev-up port-offset logic).
const platformApiBaseUrl = process.env.PLATFORM_API_BASE_URL ?? "http://localhost:18000";
const webBasePath = process.env.ANYTOOLAI_WEB_BASE_PATH;

const portalConsumerId = process.env.ANYTOOLAI_PORTAL_CONSUMER_ID ?? DEFAULT_PORTAL_CONSUMER_ID;
if (!/^[a-z][a-z0-9-]{0,63}$/.test(portalConsumerId)) throw new Error("Invalid ANYTOOLAI_PORTAL_CONSUMER_ID");

const nextConfig: NextConfig = {
  env: { NEXT_PUBLIC_ANYTOOLAI_WEB_BASE_PATH: webBasePath ?? "", NEXT_PUBLIC_PORTAL_CONSUMER_ID: portalConsumerId },
  ...(webBasePath ? { basePath: webBasePath } : {}),
  rewrites() {
    return Promise.resolve([
      {
        source: "/v1/:path*",
        destination: `${platformApiBaseUrl}/v1/:path*`,
        basePath: false,
      },
    ]);
  },
  // The canonical gate (`frontend_check()`'s `pnpm -r lint`, then its own `pnpm -r build`) already
  // lints this workspace before that `build` step runs, so without this, that path would pay for
  // a second, redundant ESLint pass here. Other direct `next build` invocations outside that gate
  // (e.g. `client_handoff_smoke()` in scripts/agent/runner.py, which builds web-mirror on its own
  // without going through `pnpm -r lint` first) don't get lint from this build step either way --
  // this flag only removes Next's own pass, it doesn't add one -- but they're still covered by
  // `full-check`'s separate, required, path-unfiltered CI job on the same PR.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
