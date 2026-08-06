/**
 * A minimal in-memory stand-in for the platform-api backend, wired as a `fetch`-compatible
 * function. It models just enough state -- guest identities, per-guest quota, and the
 * ANY-150 idempotent scenario-start ledger -- to exercise the create-guest -> quota ->
 * keyed-start -> retry -> poll flow end to end against a realistic fake server, without a real
 * cross-language backend.
 */

type ScenarioSessionRecord = {
  scenarioSessionId: string;
  jobId: string;
  status: string;
  currentCheckpointId: string | null;
  allowedNextActions: string[];
  resultArtifactId: string | null;
};

type StartLedgerEntry = {
  idempotencyKey: string;
  requestFingerprint: string;
  scenarioSessionId: string;
};

export type FakePlatformServerOptions = {
  quotaLimit?: number;
  /** How many poll GETs before the session flips from "running" to "completed". */
  pollsUntilComplete?: number;
};

export function createFakePlatformServer(options: FakePlatformServerOptions = {}) {
  const quotaLimit = options.quotaLimit ?? 3;
  const pollsUntilComplete = options.pollsUntilComplete ?? 2;

  let nextGuestSeq = 1;
  let nextSessionSeq = 1;
  const guestUsedCount = new Map<string, number>();
  const startLedger = new Map<string, StartLedgerEntry>(); // keyed by idempotencyKey
  const sessions = new Map<string, ScenarioSessionRecord>();
  const pollCounts = new Map<string, number>();

  function jsonResponse(status: number, body: unknown): Response {
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }

  function errorResponse(status: number, code: string, message: string): Response {
    return jsonResponse(status, { error: { code, message, request_id: `req_${code}` } });
  }

  const fetchImpl: typeof fetch = async (input, init) => {
    const url = new URL(String(input));
    const method = (init?.method ?? "GET").toUpperCase();
    const path = url.pathname;

    if (method === "POST" && path === "/v1/identity/guest") {
      const guestId = `guest_${nextGuestSeq}`;
      nextGuestSeq += 1;
      guestUsedCount.set(guestId, 0);
      return jsonResponse(200, { guest_id: guestId });
    }

    const quotaMatch = path.match(/^\/v1\/products\/([^/]+)\/quota$/);
    if (method === "GET" && quotaMatch) {
      const productId = decodeURIComponent(quotaMatch[1]);
      const guestId = url.searchParams.get("guest_id");
      if (!guestId || !guestUsedCount.has(guestId)) {
        return errorResponse(404, "guest_identity_not_found", "Guest identity not found.");
      }
      const usedCount = guestUsedCount.get(guestId) ?? 0;
      return jsonResponse(200, {
        guest_id: guestId,
        product_id: productId,
        quota_policy_id: "kernel_demo.guest_quota_v1",
        quota_dimension: "product",
        dimension_key: productId,
        scenario_id: null,
        unit: "scenario_run",
        period: "lifetime",
        limit_count: quotaLimit,
        used_count: usedCount,
        remaining_count: Math.max(0, quotaLimit - usedCount),
        exhausted: usedCount >= quotaLimit,
      });
    }

    const startMatch = path.match(/^\/v1\/products\/([^/]+)\/scenarios\/([^/]+)\/start$/);
    if (method === "POST" && startMatch) {
      const idempotencyKey = init?.headers ? new Headers(init.headers).get("Idempotency-Key") : null;
      if (!idempotencyKey) {
        return errorResponse(422, "idempotency_key_invalid", "Idempotency-Key is required.");
      }
      const body = JSON.parse(String(init?.body ?? "{}"));
      const guestId: string | null = body.guest_id ?? null;
      const requestFingerprint = JSON.stringify({ path, body });

      const existing = startLedger.get(idempotencyKey);
      if (existing) {
        if (existing.requestFingerprint !== requestFingerprint) {
          return errorResponse(
            409,
            "idempotency_key_conflict",
            "Idempotency-Key was already used with a different request.",
          );
        }
        const session = sessions.get(existing.scenarioSessionId)!;
        return jsonResponse(200, _startPayload(session));
      }

      if (guestId) {
        if (!guestUsedCount.has(guestId)) {
          return errorResponse(404, "guest_identity_not_found", "Guest identity not found.");
        }
        const usedCount = guestUsedCount.get(guestId) ?? 0;
        if (usedCount >= quotaLimit) {
          return errorResponse(429, "quota_exhausted", "Guest quota exhausted.");
        }
      }

      const scenarioSessionId = `scenario_session_${nextSessionSeq}`;
      const jobId = `job_${nextSessionSeq}`;
      nextSessionSeq += 1;
      const session: ScenarioSessionRecord = {
        scenarioSessionId,
        jobId,
        status: "running",
        currentCheckpointId: null,
        allowedNextActions: [],
        resultArtifactId: null,
      };
      sessions.set(scenarioSessionId, session);
      pollCounts.set(scenarioSessionId, 0);
      startLedger.set(idempotencyKey, { idempotencyKey, requestFingerprint, scenarioSessionId });
      if (guestId) {
        guestUsedCount.set(guestId, (guestUsedCount.get(guestId) ?? 0) + 1);
      }
      return jsonResponse(200, _startPayload(session));
    }

    const sessionMatch = path.match(/^\/v1\/scenario-sessions\/([^/]+)$/);
    if (method === "GET" && sessionMatch) {
      const scenarioSessionId = decodeURIComponent(sessionMatch[1]);
      const session = sessions.get(scenarioSessionId);
      if (!session) {
        return errorResponse(
          404,
          "scenario_session_not_found",
          "Scenario session not found.",
        );
      }
      const polls = (pollCounts.get(scenarioSessionId) ?? 0) + 1;
      pollCounts.set(scenarioSessionId, polls);
      if (session.status === "running" && polls >= pollsUntilComplete) {
        session.status = "completed";
        session.currentCheckpointId = "result_ready";
        session.allowedNextActions = ["copy_result"];
        session.resultArtifactId = "artifact_1";
      }
      return jsonResponse(200, _sessionPayload(session));
    }

    return jsonResponse(500, { error: { code: "unhandled_route", message: `${method} ${path}`, request_id: "req_unhandled" } });
  };

  function _startPayload(session: ScenarioSessionRecord) {
    return {
      scenario_session_id: session.scenarioSessionId,
      job_id: session.jobId,
      status: session.status,
      allowed_next_actions: session.allowedNextActions,
      result_artifact_id: session.resultArtifactId,
    };
  }

  function _sessionPayload(session: ScenarioSessionRecord) {
    return { ..._startPayload(session), current_checkpoint_id: session.currentCheckpointId };
  }

  return {
    fetchImpl,
    getUsedCount(guestId: string): number {
      return guestUsedCount.get(guestId) ?? 0;
    },
  };
}
