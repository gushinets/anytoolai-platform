import { isRecord } from "../api/parsing";
import { parsePortalOwner, samePortalOwner, type PortalOwner, type TabStorage } from "../identity/portalSession";
import type { ScenarioStartRequest } from "./types";

type RecoveryBase = { version: 1; owner: PortalOwner; productId: string; scenarioId: string };
export type PaidStartRecovery = RecoveryBase & (
  | { kind: "pending"; idempotencyKey: string; request: ScenarioStartRequest }
  | { kind: "accepted"; scenarioSessionId: string }
);
export type PaidStartPersistence = { storage: TabStorage; owner: PortalOwner; isCurrent: () => boolean };
const recoveryKey = (productId: string) => `anytoolai.paid_start.v1.${productId}`;
const identifier = (value: unknown): value is string => typeof value === "string" && /^[A-Za-z0-9_.-]{1,128}$/.test(value);

export function parsePaidStartRecovery(value: unknown): PaidStartRecovery | null {
  if (!isRecord(value) || value.version !== 1 || !identifier(value.productId) || !identifier(value.scenarioId)) return null;
  const owner = parsePortalOwner(value.owner);
  if (!owner) return null;
  const base: RecoveryBase = { version: 1, owner, productId: value.productId, scenarioId: value.scenarioId };
  if (value.kind === "accepted" && identifier(value.scenarioSessionId)) return { ...base, kind: "accepted", scenarioSessionId: value.scenarioSessionId };
  if (value.kind !== "pending" || !identifier(value.idempotencyKey) || !isRecord(value.request)) return null;
  const request = value.request;
  if (request.productId !== base.productId || request.scenarioId !== base.scenarioId || !identifier(request.frontendId) ||
    !Object.hasOwn(request, "input") || request.guestId !== undefined || request.userId !== undefined ||
    (request.sourceFrontendInstanceId !== undefined && !identifier(request.sourceFrontendInstanceId))) return null;
  return { ...base, kind: "pending", idempotencyKey: value.idempotencyKey, request: {
    productId: base.productId, scenarioId: base.scenarioId, frontendId: request.frontendId, input: request.input,
    ...(request.sourceFrontendInstanceId === undefined ? {} : { sourceFrontendInstanceId: request.sourceFrontendInstanceId }),
  } };
}

export function readPaidStartRecovery(persistence: PaidStartPersistence, productId: string): PaidStartRecovery | null {
  const raw = persistence.storage.getItem(recoveryKey(productId));
  if (!raw) return null;
  const value: unknown = JSON.parse(raw);
  const recovery = parsePaidStartRecovery(value);
  if (!recovery || recovery.productId !== productId) throw new Error("paid_recovery_invalid");
  if (!samePortalOwner(recovery.owner, persistence.owner)) {
    clearPaidStartRecovery(persistence.storage, productId);
    return null;
  }
  return recovery;
}

export class PaidStartRecoveryConflict extends Error {}

export function persistPaidStartRecovery(persistence: PaidStartPersistence, recovery: PaidStartRecovery, acceptedPendingKey?: string): void {
  if (!persistence.isCurrent() || !samePortalOwner(persistence.owner, recovery.owner)) throw new Error("paid_identity_changed");
  const current = readPaidStartRecovery(persistence, recovery.productId);
  if (current?.kind === "pending" && current.idempotencyKey !== (recovery.kind === "pending" ? recovery.idempotencyKey : acceptedPendingKey)) {
    throw new PaidStartRecoveryConflict("paid_recovery_pending");
  }
  if (acceptedPendingKey !== undefined && recovery.kind === "accepted" && current?.kind === "accepted" &&
    current.scenarioSessionId !== recovery.scenarioSessionId) throw new PaidStartRecoveryConflict("paid_recovery_pending");
  if (current?.kind === "pending" && recovery.kind === "pending" &&
    (current.scenarioId !== recovery.scenarioId || current.request.frontendId !== recovery.request.frontendId ||
      current.request.sourceFrontendInstanceId !== recovery.request.sourceFrontendInstanceId ||
      JSON.stringify(current.request.input) !== JSON.stringify(recovery.request.input))) {
    throw new PaidStartRecoveryConflict("paid_recovery_pending");
  }
  const key = recoveryKey(recovery.productId);
  const raw = JSON.stringify(recovery);
  persistence.storage.setItem(key, raw);
  // Storage adapters that silently refuse writes also fail before any new paid send.
  if (persistence.storage.getItem(key) !== raw) throw new Error("paid_storage_unavailable");
}

/** Selecting a historical result must not replace an unresolved start's only replay handle. */
export function rememberPaidResult(persistence: PaidStartPersistence, recovery: PaidStartRecovery & { kind: "accepted" }): void {
  if (!persistence.isCurrent() || !samePortalOwner(persistence.owner, recovery.owner)) throw new Error("paid_identity_changed");
  if (readPaidStartRecovery(persistence, recovery.productId)?.kind === "pending") return;
  persistPaidStartRecovery(persistence, recovery);
}

export function clearPaidStartRecovery(tabStorage: TabStorage, productId: string): void {
  tabStorage.removeItem(recoveryKey(productId));
}
