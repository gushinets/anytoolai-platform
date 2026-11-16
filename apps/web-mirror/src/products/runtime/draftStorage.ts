import type { PortalOwner } from "@anytoolai/ce-kit";

const STORAGE_VERSION = 1;
const MAX_CLOCK_SKEW_MS = 60_000;

export type StoredRun = { scenarioSessionId: string; input: unknown; startedAtMs?: number };
export type StoredDraft = { values?: unknown; run?: StoredRun };

function paidDraftScope(owner: PortalOwner): string {
  return `anytoolai.paid_draft.v1.${JSON.stringify([owner.tenantId, owner.region, owner.userId])}`;
}

export function productDraftKey(productId: string, messageScope: string, owner?: PortalOwner): string {
  const scope = owner ? paidDraftScope(owner) : "anytoolai.product_draft";
  return `${scope}.${productId}.${messageScope}`;
}

function scenarioKey(productId: string, owner?: PortalOwner): string {
  return owner ? `${paidDraftScope(owner)}.scenario.${productId}` : `anytoolai.product_draft_scenario.${productId}`;
}

/** The caller validates the saved scenario against its current opt-in definitions. */
export function readProductDraftScenario(productId: string, owner?: PortalOwner): string | undefined {
  try {
    return window.sessionStorage.getItem(scenarioKey(productId, owner)) ?? undefined;
  } catch {
    return undefined;
  }
}

export function saveProductDraftScenario(productId: string, scenarioId: string, owner?: PortalOwner): void {
  try {
    window.sessionStorage.setItem(scenarioKey(productId, owner), scenarioId);
  } catch {
    // Storage unavailable or full: the selected mode does not survive a reload.
  }
}

/** Reads and shape-checks the envelope only; product values are validated by the caller. */
export function readProductDraft(key: string): StoredDraft | undefined {
  try {
    const raw = window.sessionStorage.getItem(key);
    if (raw === null) return undefined;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null || (parsed as { v?: unknown }).v !== STORAGE_VERSION) {
      return undefined;
    }
    const { values, run } = parsed as { values?: unknown; run?: unknown };
    let validRun: StoredRun | undefined;
    if (typeof run === "object" && run !== null && "scenarioSessionId" in run &&
        typeof run.scenarioSessionId === "string" && run.scenarioSessionId.length > 0) {
      validRun = { scenarioSessionId: run.scenarioSessionId, input: "input" in run ? run.input : undefined };
      if ("startedAtMs" in run && typeof run.startedAtMs === "number" &&
          Number.isFinite(run.startedAtMs) && run.startedAtMs > 0 &&
          run.startedAtMs <= Date.now() + MAX_CLOCK_SKEW_MS) {
        validRun.startedAtMs = run.startedAtMs;
      }
    }
    return { ...(values === undefined ? {} : { values }), ...(validRun ? { run: validRun } : {}) };
  } catch {
    return undefined;
  }
}

function write(key: string, draft: StoredDraft): void {
  try {
    if (draft.values === undefined && draft.run === undefined) {
      window.sessionStorage.removeItem(key);
    } else {
      window.sessionStorage.setItem(key, JSON.stringify({ v: STORAGE_VERSION, ...draft }));
    }
  } catch {
    // Storage unavailable or full: the draft simply does not survive a reload.
  }
}

/** Replaces `values`, keeps `run`. */
export function saveDraftValues(key: string, values: unknown): void {
  const current = readProductDraft(key);
  write(key, { ...(current?.run ? { run: current.run } : {}), values });
}

/** Replaces `run` (null removes it), keeps `values`. */
export function saveDraftRun(key: string, run: StoredRun | null): void {
  const current = readProductDraft(key);
  write(key, { ...(current?.values === undefined ? {} : { values: current.values }), ...(run ? { run } : {}) });
}

export function clearProductDraft(key: string): void {
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // ignore
  }
}
