import { describe, expect, it } from "vitest";
import {
  isHandoffAcceptanceFailed,
  isHandoffExpired,
  isHandoffNotActionable,
  isIdempotencyKeyConflict,
  isQuotaExhausted,
  isResultNotFound,
  isResultUnavailable,
  isScenarioActionConflict,
} from "../../src/api/errors/classify";
import type { PlatformApiError } from "../../src/api/errors/types";

function backendError(code: string): PlatformApiError {
  return { type: "backend_error", status: 409, code, message: "x", requestId: "req_1" };
}

describe("isIdempotencyKeyConflict", () => {
  it("is true only for the idempotency_key_conflict code", () => {
    expect(isIdempotencyKeyConflict(backendError("idempotency_key_conflict"))).toBe(true);
    expect(isIdempotencyKeyConflict(backendError("scenario_checkpoint_conflict"))).toBe(false);
  });

  it("is false for non-backend_error variants", () => {
    expect(isIdempotencyKeyConflict({ type: "timeout" })).toBe(false);
    expect(isIdempotencyKeyConflict({ type: "aborted" })).toBe(false);
    expect(isIdempotencyKeyConflict({ type: "network_error", message: "x" })).toBe(false);
    expect(isIdempotencyKeyConflict({ type: "invalid_response", status: 200, message: "x" })).toBe(
      false,
    );
  });
});

describe("isScenarioActionConflict", () => {
  it("is true for checkpoint and next-action conflict codes", () => {
    expect(isScenarioActionConflict(backendError("scenario_checkpoint_conflict"))).toBe(true);
    expect(isScenarioActionConflict(backendError("scenario_checkpoint_not_actionable"))).toBe(true);
    expect(isScenarioActionConflict(backendError("scenario_next_action_not_allowed"))).toBe(true);
  });

  it("is false for idempotency_key_conflict, even though both are HTTP 409", () => {
    expect(isScenarioActionConflict(backendError("idempotency_key_conflict"))).toBe(false);
  });

  it("is false for an unrelated code", () => {
    expect(isScenarioActionConflict(backendError("scenario_session_not_found"))).toBe(false);
  });
});

describe("isQuotaExhausted", () => {
  it("is true only for the quota_exhausted code", () => {
    expect(isQuotaExhausted(backendError("quota_exhausted"))).toBe(true);
    expect(isQuotaExhausted(backendError("guest_identity_required"))).toBe(false);
  });
});

describe("isResultNotFound", () => {
  it("is true only for the result_artifact_not_found code", () => {
    expect(isResultNotFound(backendError("result_artifact_not_found"))).toBe(true);
    expect(isResultNotFound(backendError("result_artifact_unavailable"))).toBe(false);
  });

  it("is false for non-backend_error variants", () => {
    expect(isResultNotFound({ type: "timeout" })).toBe(false);
  });
});

describe("isResultUnavailable", () => {
  it("is true only for the result_artifact_unavailable code", () => {
    expect(isResultUnavailable(backendError("result_artifact_unavailable"))).toBe(true);
    expect(isResultUnavailable(backendError("result_artifact_not_found"))).toBe(false);
  });

  it("is false for an unrelated code, even though both are HTTP 404", () => {
    expect(isResultUnavailable(backendError("scenario_session_not_found"))).toBe(false);
  });
});

describe("isHandoffExpired", () => {
  it("is true only for the handoff_expired code", () => {
    expect(isHandoffExpired(backendError("handoff_expired"))).toBe(true);
    expect(isHandoffExpired(backendError("handoff_not_actionable"))).toBe(false);
  });

  it("is false for non-backend_error variants", () => {
    expect(isHandoffExpired({ type: "timeout" })).toBe(false);
  });
});

describe("isHandoffNotActionable", () => {
  it("is true for the already-accepted/declined/failed/not-actionable codes", () => {
    expect(isHandoffNotActionable(backendError("handoff_already_accepted"))).toBe(true);
    expect(isHandoffNotActionable(backendError("handoff_declined"))).toBe(true);
    expect(isHandoffNotActionable(backendError("handoff_failed"))).toBe(true);
    expect(isHandoffNotActionable(backendError("handoff_not_actionable"))).toBe(true);
  });

  it("is false for handoff_expired, even though both mean the token can't be acted on", () => {
    expect(isHandoffNotActionable(backendError("handoff_expired"))).toBe(false);
  });

  it("is false for an unrelated code", () => {
    expect(isHandoffNotActionable(backendError("handoff_not_found"))).toBe(false);
  });
});

describe("isHandoffAcceptanceFailed", () => {
  it("is true only for the handoff_acceptance_failed code", () => {
    expect(isHandoffAcceptanceFailed(backendError("handoff_acceptance_failed"))).toBe(true);
    expect(isHandoffAcceptanceFailed(backendError("handoff_failed"))).toBe(false);
  });

  it("is false for non-backend_error variants", () => {
    expect(isHandoffAcceptanceFailed({ type: "timeout" })).toBe(false);
  });
});
