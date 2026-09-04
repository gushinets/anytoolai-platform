import type { NextConfig } from "next";

// HandoffConsent.tsx/HandoffPage build their PlatformApiClient with `window.location.origin` and
// call paths like `/v1/handoffs/{token}` -- this rewrite is what makes those same-origin requests
// actually reach platform-api, whose port varies per checkout (see scripts/agent/runner.py's
// dev-up port-offset logic).
const platformApiBaseUrl = process.env.PLATFORM_API_BASE_URL ?? "http://localhost:18000";

const nextConfig: NextConfig = {
  rewrites() {
    return Promise.resolve([{ source: "/v1/:path*", destination: `${platformApiBaseUrl}/v1/:path*` }]);
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
