import type { AssertExactSchemaShape } from "../api/driftAssertions";
import type { components } from "../api/generated/platformApi";
import { isNullableString, isRecord } from "../api/parsing";
import { isQuotaDimension, isQuotaPeriod, isQuotaUnit } from "./quotaEnums";
import type { QuotaState } from "./types";

// Date.parse alone accepts strings like "5", so require an ISO date-time prefix as well.
function isIsoTimestamp(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}T/.test(value) && !Number.isNaN(Date.parse(value));
}

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
    resets_at: resetsAt,
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
  // resets_at is absent from older APIs: absent and null map to null, anything else must be an
  // ISO-8601 timestamp string (fail closed, like every other field).
  if (!isNullableString(scenarioId) || !isNullableString(resetsAt)) {
    return null;
  }
  if (typeof resetsAt === "string" && !isIsoTimestamp(resetsAt)) {
    return null;
  }
  if (!isQuotaDimension(quotaDimension) || !isQuotaUnit(unit) || !isQuotaPeriod(period)) {
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
    resetsAt: resetsAt ?? null,
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
    period: components["schemas"]["QuotaPeriod"];
    product_id: string;
    quota_dimension: components["schemas"]["QuotaDimension"];
    quota_policy_id: string;
    remaining_count: number;
    resets_at?: string | null;
    scenario_id?: string | null;
    unit: components["schemas"]["QuotaUnit"];
    used_count: number;
  }
>;
const _assertQuotaStateShapeMatchesGenerated: _QuotaStateShapeCheck = true;
void _assertQuotaStateShapeMatchesGenerated;
