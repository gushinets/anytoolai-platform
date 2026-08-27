import type { NextConfig } from "next";

// HandoffConsent.tsx/HandoffPage build their PlatformApiClient with `window.location.origin` and
// call paths like `/v1/handoffs/{token}` -- this rewrite is what makes those same-origin requests
// actually reach platform-api, whose port varies per checkout (see scripts/agent/runner.py's
// dev-up port-offset logic).
const platformApiBaseUrl = process.env.PLATFORM_API_BASE_URL ?? "http://localhost:18000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/v1/:path*", destination: `${platformApiBaseUrl}/v1/:path*` }];
  },
};

export default nextConfig;
