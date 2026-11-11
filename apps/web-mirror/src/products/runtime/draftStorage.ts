const STORAGE_VERSION = 1;

export type StoredRun = { scenarioSessionId: string; input: unknown };
export type StoredDraft = { values?: unknown; run?: StoredRun };

export function productDraftKey(productId: string, messageScope: string): string {
  return `anytoolai.product_draft.${productId}.${messageScope}`;
}

/** The caller validates the saved scenario against its current opt-in definitions. */
export function readProductDraftScenario(productId: string): string | undefined {
  try {
    return window.sessionStorage.getItem(`anytoolai.product_draft_scenario.${productId}`) ?? undefined;
  } catch {
    return undefined;
  }
}

export function saveProductDraftScenario(productId: string, scenarioId: string): void {
  try {
    window.sessionStorage.setItem(`anytoolai.product_draft_scenario.${productId}`, scenarioId);
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
    const validRun =
      typeof run === "object" && run !== null &&
      typeof (run as StoredRun).scenarioSessionId === "string" &&
      (run as StoredRun).scenarioSessionId.length > 0
        ? { scenarioSessionId: (run as StoredRun).scenarioSessionId, input: (run as StoredRun).input }
        : undefined;
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
