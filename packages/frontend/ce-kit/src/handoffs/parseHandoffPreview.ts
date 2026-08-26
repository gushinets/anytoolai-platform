import type { AssertExactSchemaShape } from "../api/driftAssertions";
import type { components } from "../api/generated/platformApi";
import { isRecord } from "../api/parsing";
import type { HandoffPreview } from "./types";

/**
 * Validates and maps the backend's `HandoffPreviewResponse` payload (snake_case) into the
 * client's `HandoffPreview` shape (camelCase). Shared by `getHandoff()`, `acceptHandoff()`, and
 * `declineHandoff()` -- all three routes return this identical shape. Returns null for anything
 * that doesn't match, so callers fall back to `invalid_response` instead of trusting arbitrary
 * payload content.
 */
export function parseHandoffPreview(payload: unknown): HandoffPreview | null {
  if (!isRecord(payload)) {
    return null;
  }

  const {
    handoff_id: handoffId,
    status,
    source_product_id: sourceProductId,
    source_product_display_name: sourceProductDisplayName,
    target_product_id: targetProductId,
    target_product_display_name: targetProductDisplayName,
    target_scenario_id: targetScenarioId,
    preview,
    expires_at: expiresAt,
    target_scenario_session_id: targetScenarioSessionId,
    target_job_id: targetJobId,
  } = payload;

  if (
    typeof handoffId !== "string" ||
    typeof status !== "string" ||
    typeof sourceProductId !== "string" ||
    typeof sourceProductDisplayName !== "string" ||
    typeof targetProductId !== "string" ||
    typeof targetProductDisplayName !== "string" ||
    typeof targetScenarioId !== "string" ||
    !isRecord(preview) ||
    Array.isArray(preview) ||
    typeof expiresAt !== "string"
  ) {
    return null;
  }
  // `target_scenario_session_id`/`target_job_id` are optional-and-nullable on the wire -- an
  // absent key and an explicit null both mean "no target session/job yet" (pre-acceptance).
  if (
    targetScenarioSessionId !== undefined &&
    targetScenarioSessionId !== null &&
    typeof targetScenarioSessionId !== "string"
  ) {
    return null;
  }
  if (targetJobId !== undefined && targetJobId !== null && typeof targetJobId !== "string") {
    return null;
  }

  return {
    handoffId,
    status,
    sourceProductId,
    sourceProductDisplayName,
    targetProductId,
    targetProductDisplayName,
    targetScenarioId,
    preview,
    expiresAt,
    targetScenarioSessionId: targetScenarioSessionId ?? null,
    targetJobId: targetJobId ?? null,
  };
}

// Compile-time drift check: fails typecheck if the backend's HandoffPreviewResponse schema grows,
// loses, retypes, or changes the nullability/optionality of a field parseHandoffPreview() above
// doesn't know about.
type _HandoffPreviewResponseShapeCheck = AssertExactSchemaShape<
  components["schemas"]["HandoffPreviewResponse"],
  {
    expires_at: string;
    handoff_id: string;
    preview: { [key: string]: unknown };
    source_product_display_name: string;
    source_product_id: string;
    status: string;
    target_job_id?: string | null;
    target_product_display_name: string;
    target_product_id: string;
    target_scenario_id: string;
    target_scenario_session_id?: string | null;
  }
>;
const _assertHandoffPreviewResponseShapeMatchesGenerated: _HandoffPreviewResponseShapeCheck = true;
void _assertHandoffPreviewResponseShapeMatchesGenerated;
