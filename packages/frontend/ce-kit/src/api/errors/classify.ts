import type { BackendApiError, PlatformApiError } from "./types";

/**
 * Known `backend_error` codes CE-kit callers need to branch on. Both `idempotency_key_conflict`
 * and the checkpoint/next-action conflicts below share HTTP 409, so callers must not distinguish
 * them by status code -- see isIdempotencyKeyConflict() / isScenarioActionConflict() below, which
 * are the reusable, tested way to do it (ANY-150).
 */
export const BACKEND_ERROR_CODE = {
  idempotencyKeyConflict: "idempotency_key_conflict",
  scenarioCheckpointConflict: "scenario_checkpoint_conflict",
  scenarioCheckpointNotActionable: "scenario_checkpoint_not_actionable",
  scenarioNextActionNotAllowed: "scenario_next_action_not_allowed",
  quotaExhausted: "quota_exhausted",
} as const;

function _isBackendErrorWithCode(
  error: PlatformApiError,
  code: string,
): error is BackendApiError {
  return error.type === "backend_error" && error.code === code;
}

/** True only for the 409 that means "retry with a new Idempotency-Key or the original request." */
export function isIdempotencyKeyConflict(error: PlatformApiError): boolean {
  return _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.idempotencyKeyConflict);
}

/**
 * True for the 409s that mean the scenario session's checkpoint/next-action state moved on --
 * distinct from `isIdempotencyKeyConflict()` even though both surface as HTTP 409.
 */
export function isScenarioActionConflict(error: PlatformApiError): boolean {
  return (
    _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.scenarioCheckpointConflict) ||
    _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.scenarioCheckpointNotActionable) ||
    _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.scenarioNextActionNotAllowed)
  );
}

/** True only for the 429 that means the guest has no quota left; no session/job was created. */
export function isQuotaExhausted(error: PlatformApiError): boolean {
  return _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.quotaExhausted);
}
