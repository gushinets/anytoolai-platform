import { makeEnumGuard } from "../api/parsing";
import type { components } from "../api/generated/platformApi";

/**
 * ANY-17 v1 web-event allowlist -- the only event types `POST /v1/client-events` accepts. Derived
 * from the generated `WebClientEventType` schema (backed by a Core `StrEnum`, not a plain `str`,
 * per docs/agent/coding-conventions.md), so a backend allowlist change fails typecheck here instead
 * of silently drifting from an independent hand-maintained copy.
 */
export type WebClientEventType = components["schemas"]["WebClientEventType"];

/**
 * The exhaustive value map below still fails typecheck (via `makeEnumGuard`'s type signature) if
 * the generated `WebClientEventType` gains or loses a member -- this file just isn't the one
 * inventing the member list anymore.
 */
export const isWebClientEventType = makeEnumGuard<WebClientEventType>({
  "web.product_viewed": true,
  "web.form_started": true,
  "web.form_submitted": true,
  "web.result_viewed": true,
  "web.retry_clicked": true,
  "web.mode_selected": true,
  "web.gap_selected": true,
  "web.feedback_submitted": true,
});
