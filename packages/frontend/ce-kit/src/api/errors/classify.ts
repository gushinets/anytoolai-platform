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
  resultArtifactNotFound: "result_artifact_not_found",
  resultArtifactUnavailable: "result_artifact_unavailable",
  handoffNotFound: "handoff_not_found",
  handoffSourceInvalid: "handoff_source_invalid",
  handoffTargetSchemaInvalid: "handoff_target_schema_invalid",
  handoffExpired: "handoff_expired",
  handoffAlreadyAccepted: "handoff_already_accepted",
  handoffDeclined: "handoff_declined",
  handoffFailed: "handoff_failed",
  handoffNotActionable: "handoff_not_actionable",
  handoffAcceptanceFailed: "handoff_acceptance_failed",
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

/** True only for the 404 that means the result artifact id is unknown, or out of tenant/region scope. */
export function isResultNotFound(error: PlatformApiError): boolean {
  return _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.resultArtifactNotFound);
}

/**
 * True only for the 404 that means the id is a real artifact but not an available canonical
 * frontend-safe result (raw/debug artifact, unfinished job, or a schema/version mismatch) --
 * distinct from `isResultNotFound()` even though both surface as HTTP 404.
 */
export function isResultUnavailable(error: PlatformApiError): boolean {
  return _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.resultArtifactUnavailable);
}

/** True only for the 404 that means the handoff_definition_id or the handoff_token is unknown. */
export function isHandoffNotFound(error: PlatformApiError): boolean {
  return _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.handoffNotFound);
}

/**
 * True for the source-session-invalid case, whether raised as the 404 from `createHandoff()` (the
 * source scenario session/artifact was never eligible) or the 500 `acceptHandoff()` can raise if
 * the source session went away between handoff creation and acceptance -- the backend marks the
 * handoff `failed` in that second case, so treat it the same as `isHandoffAcceptanceFailed()`:
 * refetch and render the resulting terminal state instead of retrying.
 */
export function isHandoffSourceInvalid(error: PlatformApiError): boolean {
  return _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.handoffSourceInvalid);
}

/** True only for the 409 that means the target schema for the handoff definition is invalid. */
export function isHandoffTargetSchemaInvalid(error: PlatformApiError): boolean {
  return _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.handoffTargetSchemaInvalid);
}

/**
 * True only for the 410 that means the handoff token has expired. Only `acceptHandoff()`/
 * `declineHandoff()` can raise it as an error -- `getHandoff()` never rejects on expiry, it always
 * returns 200 with `status` reflecting the expired token instead.
 */
export function isHandoffExpired(error: PlatformApiError): boolean {
  return _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.handoffExpired);
}

/**
 * True for the 409s that mean the token is no longer actionable (already accepted/declined, the
 * target failed, or a generic not-actionable state) -- one guard, not four, since the correct UI
 * response to all of them is identical: refetch via `getHandoff()` and trust its authoritative
 * `status` instead of retrying the mutation.
 */
export function isHandoffNotActionable(error: PlatformApiError): boolean {
  return (
    _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.handoffAlreadyAccepted) ||
    _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.handoffDeclined) ||
    _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.handoffFailed) ||
    _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.handoffNotActionable)
  );
}

/** True only for the 500 that means accepting the handoff failed while executing the target. */
export function isHandoffAcceptanceFailed(error: PlatformApiError): boolean {
  return _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.handoffAcceptanceFailed);
}
