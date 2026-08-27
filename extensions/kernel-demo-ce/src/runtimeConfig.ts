// Per-checkout dev-up ports vary (scripts/agent/runner.py derives an offset from the repo path),
// so these are build-time overrides rather than hardcoded -- the smoke harness sets them to match
// the actual dev-up/next-dev ports before running `wxt build`.
export const runtimeConfig = {
  platformApiBaseUrl: import.meta.env.WXT_PLATFORM_API_BASE_URL ?? "http://localhost:18000",
  webConsentBaseUrl: import.meta.env.WXT_WEB_CONSENT_BASE_URL ?? "http://localhost:3000",
};
