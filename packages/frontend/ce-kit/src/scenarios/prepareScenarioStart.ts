import { requestAndParse } from "../api/client";
import type { PlatformApiClient, PlatformApiRequestOptions, PlatformApiResult } from "../api/client";
import { generateIdempotencyKey } from "./idempotencyKey";
import { parseScenarioStartResponse } from "./parseScenarioSessionSnapshot";
import type { ScenarioSessionSnapshot, ScenarioStartRequest } from "./types";
import { clearPaidStartRecovery, PaidStartRecoveryConflict, persistPaidStartRecovery, readPaidStartRecovery, type PaidStartPersistence, type PaidStartRecovery } from "./paidStartRecovery";
import { samePortalOwner } from "../identity/portalSession";

/** Independent of the client's own timeout; cancels this attempt only. */
export type PreparedScenarioStartExecuteOptions = Pick<
  PlatformApiRequestOptions,
  "signal" | "timeoutMs"
>;

/**
 * An opaque, retryable handle for one logical scenario-start submission (ANY-150).
 *
 * `prepareScenarioStart()` generates one `Idempotency-Key` up front; every `execute()` call on
 * the same handle -- including explicit retries of an ambiguous failure -- reuses that key, so
 * the backend can collapse duplicate submits into the original session/job instead of consuming
 * quota twice. Calling code never sees or manages the key or its header directly. To submit a
 * genuinely new request, call `prepareScenarioStart()` again to get a new key.
 */
export type PreparedScenarioStart = {
  /** Forget only this operation after a definitive outcome; unresolved sends must retain recovery. */
  forgetRecovery(): void;
  execute(
    client: PlatformApiClient,
    options?: PreparedScenarioStartExecuteOptions,
  ): Promise<PlatformApiResult<ScenarioSessionSnapshot>>;
};

export function prepareScenarioStart(request: ScenarioStartRequest, persistence?: PaidStartPersistence): PreparedScenarioStart {
  return prepareWithKey(request, generateIdempotencyKey(), persistence);
}

export function restorePaidScenarioStart(recovery: PaidStartRecovery & { kind: "pending" }, persistence: PaidStartPersistence): PreparedScenarioStart {
  return prepareWithKey(recovery.request, recovery.idempotencyKey, persistence);
}

function prepareWithKey(request: ScenarioStartRequest, idempotencyKey: string, persistence?: PaidStartPersistence): PreparedScenarioStart {
  const frozenRequest = structuredClone(request);
  let acceptedSessionId: string | undefined;
  // Snapshotted once, here, rather than read from `request` inside `execute()`: a retry must
  // resend exactly the same payload as the original submission even if the caller mutates (or
  // reuses a form-bound) `request` object between two `execute()` calls on this handle --
  // otherwise the same `Idempotency-Key` would go out attached to two different bodies.
  const path = `/v1/products/${encodeURIComponent(request.productId)}/scenarios/${encodeURIComponent(request.scenarioId)}/start`;
  const body = {
    frontend_id: request.frontendId,
    input: structuredClone(request.input),
    guest_id: request.guestId ?? null,
    user_id: request.userId ?? null,
    source_frontend_instance_id: request.sourceFrontendInstanceId ?? null,
  };

  return {
    forgetRecovery() {
      if (!persistence || !persistence.isCurrent()) return;
      const saved = readPaidStartRecovery(persistence, frozenRequest.productId);
      if ((saved?.kind === "pending" && saved.idempotencyKey === idempotencyKey) ||
        (saved?.kind === "accepted" && saved.scenarioSessionId === acceptedSessionId)) {
        clearPaidStartRecovery(persistence.storage, frozenRequest.productId);
      }
    },
    async execute(client, options) {
      if (client.portalIdentity && (!persistence || !samePortalOwner(client.portalIdentity.owner, persistence.owner))) {
        return { ok: false, error: { type: "local_error", code: "paid_storage_unavailable" } };
      }
      if (persistence) {
        if (!persistence.isCurrent()) return { ok: false, error: { type: "aborted" } };
        try {
          persistPaidStartRecovery(persistence, { version: 1, kind: "pending", owner: persistence.owner,
            productId: frozenRequest.productId, scenarioId: frozenRequest.scenarioId, idempotencyKey, request: frozenRequest });
        } catch (error) {
          return { ok: false, error: { type: "local_error", code: error instanceof PaidStartRecoveryConflict ? "paid_recovery_pending" : "paid_storage_unavailable" } };
        }
      }
      const result = await requestAndParse(
        client,
        {
          method: "POST",
          path,
          body,
          headers: { "Idempotency-Key": idempotencyKey },
          signal: options?.signal,
          timeoutMs: options?.timeoutMs,
        },
        parseScenarioStartResponse,
        "Scenario start response was invalid.",
      );
      if (persistence && !persistence.isCurrent()) return { ok: false, error: { type: "aborted" } };
      if (persistence && result.ok) {
        acceptedSessionId = result.value.scenarioSessionId;
        try {
          persistPaidStartRecovery(persistence, { version: 1, kind: "accepted", owner: persistence.owner,
            productId: frozenRequest.productId, scenarioId: frozenRequest.scenarioId, scenarioSessionId: result.value.scenarioSessionId }, idempotencyKey);
        } catch {
          // Acceptance already happened. Retain the current descriptor if storage failed or
          // a newer operation owns it; this response still opens its accepted result.
        }
      }
      return result;
    },
  };
}
