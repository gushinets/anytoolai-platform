import type { AssertExactSchemaShape } from "../api/driftAssertions";
import type { components } from "../api/generated/platformApi";
import { isNullableString, isRecord } from "../api/parsing";
import type { QuotaState } from "./types";

/**
 * Validates and maps the backend's `QuotaStateResponse` payload (snake_case) into the client's
 * `QuotaState` shape (camelCase). Returns null for anything that doesn't match, so callers fall
 * back to `invalid_response` instead of trusting arbitrary payload content.
 */
export function parseQuotaState(payload: unknown): QuotaState | null {
  if (!isRecord(payload)) {
    return null;
  }

  const {
    guest_id: guestId,
    product_id: productId,
    quota_policy_id: quotaPolicyId,
    quota_dimension: quotaDimension,
    dimension_key: dimensionKey,
    scenario_id: scenarioId,
    unit,
    period,
    limit_count: limitCount,
    used_count: usedCount,
    remaining_count: remainingCount,
    exhausted,
  } = payload;

  if (
    typeof guestId !== "string" ||
    typeof productId !== "string" ||
    typeof quotaPolicyId !== "string" ||
    typeof quotaDimension !== "string" ||
    typeof dimensionKey !== "string" ||
    typeof unit !== "string" ||
    typeof period !== "string" ||
    typeof limitCount !== "number" ||
    typeof usedCount !== "number" ||
    typeof remainingCount !== "number" ||
    typeof exhausted !== "boolean"
  ) {
    return null;
  }
  if (!isNullableString(scenarioId)) {
    return null;
  }

  return {
    guestId,
    productId,
    quotaPolicyId,
    quotaDimension,
    dimensionKey,
    scenarioId: scenarioId ?? null,
    unit,
    period,
    limitCount,
    usedCount,
    remainingCount,
    exhausted,
  };
}

// Compile-time drift check: fails typecheck if the backend's QuotaStateResponse schema grows,
// loses, retypes, or changes the nullability/optionality of a field that parseQuotaState() above
// doesn't know about.
type _QuotaStateShapeCheck = AssertExactSchemaShape<
  components["schemas"]["QuotaStateResponse"],
  {
    dimension_key: string;
    exhausted: boolean;
    guest_id: string;
    limit_count: number;
    period: string;
    product_id: string;
    quota_dimension: string;
    quota_policy_id: string;
    remaining_count: number;
    scenario_id?: string | null;
    unit: string;
    used_count: number;
  }
>;
const _assertQuotaStateShapeMatchesGenerated: _QuotaStateShapeCheck = true;
void _assertQuotaStateShapeMatchesGenerated;
