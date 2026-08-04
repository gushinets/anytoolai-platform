import type { QuotaState } from "./types";

function _isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * Validates and maps the backend's `QuotaStateResponse` payload (snake_case) into the client's
 * `QuotaState` shape (camelCase). Returns null for anything that doesn't match, so callers fall
 * back to `invalid_response` instead of trusting arbitrary payload content.
 */
export function parseQuotaState(payload: unknown): QuotaState | null {
  if (!_isRecord(payload)) {
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
  if (scenarioId !== null && scenarioId !== undefined && typeof scenarioId !== "string") {
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
