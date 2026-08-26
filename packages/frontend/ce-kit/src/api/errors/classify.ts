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

function _isBackendErrorWithCodeAndStatus(
  error: PlatformApiError,
  code: string,
  status: number,
): error is BackendApiError {
  return _isBackendErrorWithCode(error, code) && error.status === status;
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
 * True whenever the backend returns `handoff_source_invalid`, regardless of context: the 404
 * `createHandoff()` raises when the source scenario session/artifact was never eligible, or either
 * of the two distinct cases `acceptHandoff()` can separately raise the same code for (see
 * `isHandoffGuestIdentityInvalid()`'s 404 and `isHandoffAcceptanceSourceInvalid()`'s 500).
 * Deliberately status-agnostic, matching every other guard in this file that classifies by `code`
 * alone.
 *
 * Do NOT treat a true result here as uniformly refetchable/terminal for an `acceptHandoff()`
 * error -- the 404 case leaves the handoff record non-terminal (refetching would just return the
 * same actionable preview), while only the 500 case is. Callers handling `acceptHandoff()` results
 * should use `isHandoffGuestIdentityInvalid()`/`isHandoffAcceptanceSourceInvalid()` instead, which
 * already encode that distinction -- see `HandoffConsent.tsx`'s `resolveActionError()`.
 */
export function isHandoffSourceInvalid(error: PlatformApiError): boolean {
  return _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.handoffSourceInvalid);
}

/** True only for the 409 that means the target schema for the handoff definition is invalid. */
export function isHandoffTargetSchemaInvalid(error: PlatformApiError): boolean {
  return _isBackendErrorWithCode(error, BACKEND_ERROR_CODE.handoffTargetSchemaInvalid);
}

/**
 * True only for the 404 `handoff_source_invalid` that `acceptHandoff()` raises *before* claiming
 * the handoff, when the accepting guest id itself doesn't resolve on the backend (e.g. a
 * persisted-but-since-deleted guest -- `createGuestIdentity()` caches a guest id in `localStorage`
 * with no server-side revalidation). The record stays non-terminal, so this is deterministic and
 * permanent for that guest id: refetching or retrying with the same stale id repeats the same 404
 * forever. Callers must clear the persisted guest id and resolve a fresh one before retrying --
 * see `HandoffConsent.tsx`'s `resolveActionError()`. Distinct from `isHandoffAcceptanceSourceInvalid()`,
 * which the backend reuses the same `handoff_source_invalid` code for, for an unrelated 500 case.
 */
export function isHandoffGuestIdentityInvalid(error: PlatformApiError): boolean {
  return _isBackendErrorWithCodeAndStatus(error, BACKEND_ERROR_CODE.handoffSourceInvalid, 404);
}

/**
 * True only for the 500 `handoff_source_invalid` that `acceptHandoff()` raises *after* claiming
 * the handoff, when the source scenario session vanished between handoff creation and acceptance.
 * The backend marks the record `failed` in this case, so it's a genuine terminal status a refetch
 * via `getHandoff()` will land on -- unlike `isHandoffGuestIdentityInvalid()`'s 404 case, which
 * leaves the record non-terminal.
 */
export function isHandoffAcceptanceSourceInvalid(error: PlatformApiError): boolean {
  return _isBackendErrorWithCodeAndStatus(error, BACKEND_ERROR_CODE.handoffSourceInvalid, 500);
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

/**
 * True for every accept()/decline() error that should be handled by refetching via getHandoff()
 * and rendering its authoritative `status`, rather than retrying the mutation or showing a generic
 * inline error: expiry, the not-actionable family, acceptance execution failure, an unknown token
 * (accept()/decline() reach the same token lookup getHandoff() uses), the terminal (500) form of
 * source-session invalidation, and quota exhaustion.
 *
 * Deliberately excludes `isHandoffGuestIdentityInvalid()`'s 404 case -- refetching that would just
 * return the same non-terminal, actionable preview -- see that guard's docstring.
 */
export function isHandoffActionRefetchable(error: PlatformApiError): boolean {
  return (
    isHandoffExpired(error) ||
    isHandoffNotActionable(error) ||
    isHandoffAcceptanceFailed(error) ||
    isHandoffNotFound(error) ||
    isHandoffAcceptanceSourceInvalid(error) ||
    isQuotaExhausted(error)
  );
}
