import { joinUrl, normalizeBaseUrl } from "../api/client/url";
import type { Navigate } from "./navigation";

export type OpenHandoffConsentOptions = {
  /** Caller-supplied web-mirror origin -- CE-kit does not invent or hardcode a deployed URL. */
  webConsentBaseUrl: string;
  /** The opaque token from `createHandoff()`. Only ever used as an opaque path segment -- never parsed. */
  handoffToken: string;
  navigate: Navigate;
};

/**
 * Builds the backend-owned handoff consent URL (`{base}/handoff/{token}`) and hands it to the
 * injected `navigate`. Not a network call. Per `docs/architecture/frontend-boundaries.md`, must
 * not log the built URL or token, and must only percent-encode the token as an opaque path
 * segment -- never derive or inspect its contents.
 *
 * Deliberately not `async`: an empty/whitespace-only `webConsentBaseUrl` must throw synchronously,
 * mirroring `PlatformApiClient`'s/`normalizeBaseUrl()`'s existing behavior, not reject a promise.
 */
export function openHandoffConsent(options: OpenHandoffConsentOptions): void | Promise<void> {
  const baseUrl = normalizeBaseUrl(options.webConsentBaseUrl);
  const url = joinUrl(baseUrl, `/handoff/${encodeURIComponent(options.handoffToken)}`);
  return options.navigate(url);
}
