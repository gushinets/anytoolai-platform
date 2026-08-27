import { describe, expect, it } from "vitest";
import {
  isHandoffAcceptanceFailed,
  isHandoffAcceptanceSourceInvalid,
  isHandoffActionRefetchable,
  isHandoffExpired,
  isHandoffGuestIdentityInvalid,
  isHandoffNotActionable,
  isIdempotencyKeyConflict,
  isQuotaExhausted,
  isResultNotFound,
  isResultUnavailable,
  isScenarioActionConflict,
} from "../../src/api/errors/classify";
import type { PlatformApiError } from "../../src/api/errors/types";

function backendError(code: string, status = 409): PlatformApiError {
  return { type: "backend_error", status, code, message: "x", requestId: "req_1" };
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

describe("isHandoffGuestIdentityInvalid", () => {
  it("is true only for the 404 handoff_source_invalid (pre-claim, accepting guest id doesn't resolve)", () => {
    expect(isHandoffGuestIdentityInvalid(backendError("handoff_source_invalid", 404))).toBe(true);
  });

  it("is false for the 500 handoff_source_invalid, even though the code is identical", () => {
    expect(isHandoffGuestIdentityInvalid(backendError("handoff_source_invalid", 500))).toBe(false);
  });

  it("is false for an unrelated code", () => {
    expect(isHandoffGuestIdentityInvalid(backendError("handoff_not_found", 404))).toBe(false);
  });
});

describe("isHandoffAcceptanceSourceInvalid", () => {
  it("is true only for the 500 handoff_source_invalid (post-claim, source session vanished)", () => {
    expect(isHandoffAcceptanceSourceInvalid(backendError("handoff_source_invalid", 500))).toBe(true);
  });

  it("is false for the 404 handoff_source_invalid, even though the code is identical", () => {
    expect(isHandoffAcceptanceSourceInvalid(backendError("handoff_source_invalid", 404))).toBe(false);
  });
});

describe("isHandoffActionRefetchable", () => {
  it("is true for expiry, not-actionable, acceptance-failure, not-found, and quota codes", () => {
    expect(isHandoffActionRefetchable(backendError("handoff_expired"))).toBe(true);
    expect(isHandoffActionRefetchable(backendError("handoff_already_accepted"))).toBe(true);
    expect(isHandoffActionRefetchable(backendError("handoff_acceptance_failed"))).toBe(true);
    expect(isHandoffActionRefetchable(backendError("quota_exhausted"))).toBe(true);
  });

  it("is true for handoff_not_found, since accept()/decline() reach the same token lookup as getHandoff()", () => {
    expect(isHandoffActionRefetchable(backendError("handoff_not_found"))).toBe(true);
  });

  it("is true for the 500 handoff_source_invalid (terminal: source session vanished post-claim)", () => {
    expect(isHandoffActionRefetchable(backendError("handoff_source_invalid", 500))).toBe(true);
  });

  it("is false for the 404 handoff_source_invalid accept() raises pre-claim (non-terminal: accepting guest id doesn't resolve)", () => {
    expect(isHandoffActionRefetchable(backendError("handoff_source_invalid", 404))).toBe(false);
  });

  it("is false for an unrelated code", () => {
    expect(isHandoffActionRefetchable(backendError("some_unexpected_code"))).toBe(false);
  });

  it("is false for non-backend_error variants", () => {
    expect(isHandoffActionRefetchable({ type: "timeout" })).toBe(false);
  });
});
