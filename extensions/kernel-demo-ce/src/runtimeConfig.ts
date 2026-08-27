// `??` alone only guards null/undefined -- an env var templated to an empty string (e.g. an unset
// CI/`.env` substitution) would otherwise silently become "", sending every PlatformApiClient
// request to this extension's own chrome-extension:// origin instead of the documented default.
function envOrDefault(value: string | undefined, fallback: string): string {
  return value || fallback;
}

// Per-checkout dev-up ports vary (scripts/agent/runner.py derives an offset from the repo path),
// so these are build-time overrides rather than hardcoded -- the smoke harness sets them to match
// the actual dev-up/next-dev ports before running `wxt build`.
export const runtimeConfig = {
  platformApiBaseUrl: envOrDefault(import.meta.env.WXT_PLATFORM_API_BASE_URL, "http://localhost:18000"),
  webConsentBaseUrl: envOrDefault(import.meta.env.WXT_WEB_CONSENT_BASE_URL, "http://localhost:3000"),
};
