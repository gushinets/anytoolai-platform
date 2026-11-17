import { getQuota, type PlatformApiClient, type QuotaRequest, type QuotaState, type RuntimeQuotaSummary } from "@anytoolai/ce-kit";

export type QuotaAdmissionSnapshot = {
  status: "unknown" | "checking" | "available" | "exhausted";
  quota: QuotaState | null;
};

export const UNKNOWN_QUOTA: QuotaAdmissionSnapshot = { status: "unknown", quota: null };

const BLOCKS_NEW_RUN: Record<QuotaAdmissionSnapshot["status"], boolean> = {
  unknown: false,
  checking: true,
  available: false,
  exhausted: true,
};

/** One quota scope, shared across forms but never across page visits or guests. */
export class QuotaAdmission {
  private snapshot = UNKNOWN_QUOTA;
  private generation = 0;
  private pending = false;
  private listeners = new Set<() => void>();

  constructor(private client: PlatformApiClient, private request: QuotaRequest) {}

  getSnapshot = (): QuotaAdmissionSnapshot => this.snapshot;
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  blocksNewRun = (): boolean => BLOCKS_NEW_RUN[this.snapshot.status];

  private publish(snapshot: QuotaAdmissionSnapshot): void {
    this.snapshot = snapshot;
    for (const listener of this.listeners) listener();
  }

  markExhausted(): void {
    // An authoritative START rejection supersedes any earlier advisory read.
    ++this.generation;
    this.pending = false;
    this.publish({ status: "exhausted", quota: null });
  }

  refresh(reason: "advisory" | "execution"): void {
    // A mode remount/New task must not supersede a post-execution read with an advisory one.
    if (reason === "advisory" && this.pending) return;
    const generation = ++this.generation;
    this.pending = true;
    const exhausted = this.snapshot.status === "exhausted";
    if (reason === "execution" && !exhausted) {
      this.publish({ ...this.snapshot, status: "checking" });
    }
    const settle = (quota: QuotaState | null) => {
      if (generation !== this.generation) return;
      this.pending = false;
      this.publish({
        quota: quota ?? this.snapshot.quota,
        status: quota ? (quota.exhausted ? "exhausted" : "available") : exhausted ? "exhausted" : "unknown",
      });
    };
    // The API client bounds this read; a form unmount must not discard the page's pending answer.
    void getQuota(this.client, this.request).then((result) => settle(result.ok ? result.value : null), () => settle(null));
  }
}

/** The shell owns this store; standalone multi-mode products own it above their keyed form. */
export class ProductQuotaStore {
  private clients = new WeakMap<PlatformApiClient, Map<string, QuotaAdmission>>();

  get(client: PlatformApiClient, request: QuotaRequest, policy: RuntimeQuotaSummary): QuotaAdmission {
    let scopes = this.clients.get(client);
    if (!scopes) {
      scopes = new Map();
      this.clients.set(client, scopes);
    }
    const key = JSON.stringify([
      request.guestId, request.productId, policy.quotaPolicyId, policy.dimension,
      policy.dimension === "scenario" ? request.scenarioId : null,
    ]);
    let admission = scopes.get(key);
    if (!admission) {
      admission = new QuotaAdmission(client, request);
      scopes.set(key, admission);
    }
    return admission;
  }
}
