import type { PlatformApiClient, PlatformApiResult } from "../api/client";
import { abortedError, timeoutError } from "../api/errors";
import { getScenarioSession } from "./getScenarioSession";
import type { ScenarioSessionStatus } from "./scenarioSessionStatus";
import type { ScenarioSession } from "./types";

/**
 * Statuses that stop polling. `waiting_for_user` stops here too (not just the workflow-terminal
 * statuses) because it means the frontend must call `nextAction()` next -- continuing to poll
 * would just idle until `maxDurationMs`. See docs/architecture/scenario-session-model.md.
 *
 * A `Record<ScenarioSessionStatus, boolean>` literal, not a hand-written `Set` -- this fails to
 * typecheck if `ScenarioSessionStatus` gains or loses a member and this map isn't updated to
 * classify it, so a new stop status can't silently fall through as non-stopping the way it could
 * with `ReadonlySet<ScenarioSessionStatus>.has()` (any subset of the union typechecks there).
 */
const SCENARIO_SESSION_STATUS_STOPS_POLLING: Record<ScenarioSessionStatus, boolean> = {
  started: false,
  running: false,
  waiting_for_user: true,
  completed: true,
  failed: true,
  expired: true,
};

const DEFAULT_INTERVAL_MS = 2_000;
const DEFAULT_MAX_DURATION_MS = 60_000;

export type PollScenarioSessionOptions = {
  intervalMs?: number;
  maxDurationMs?: number;
  signal?: AbortSignal;
};

export type PollScenarioSessionStopReason = "session_status" | "error" | "timeout" | "aborted";

export type PollScenarioSessionResult = {
  reason: PollScenarioSessionStopReason;
  result: PlatformApiResult<ScenarioSession>;
};

/**
 * Bounded, cancellable polling of `getScenarioSession()`. Never starts, replays, or configures
 * workflow/LLM execution -- it only reads backend-owned session state until a stop status is
 * reached, the caller's `signal` aborts, or `maxDurationMs` elapses.
 */
export async function pollScenarioSession(
  client: PlatformApiClient,
  scenarioSessionId: string,
  options?: PollScenarioSessionOptions,
): Promise<PollScenarioSessionResult> {
  const intervalMs = options?.intervalMs ?? DEFAULT_INTERVAL_MS;
  const maxDurationMs = options?.maxDurationMs ?? DEFAULT_MAX_DURATION_MS;
  const signal = options?.signal;
  const startedAt = Date.now();
  let lastResult: PlatformApiResult<ScenarioSession> | null = null;

  for (;;) {
    if (signal?.aborted) {
      return { reason: "aborted", result: { ok: false, error: abortedError() } };
    }

    // Checked *before* issuing another GET, not just after one finishes -- otherwise a request
    // started right at the deadline (e.g. right after the interval sleep) would still be allowed
    // to run.
    const remainingBeforeRequestMs = maxDurationMs - (Date.now() - startedAt);
    if (remainingBeforeRequestMs <= 0) {
      return { reason: "timeout", result: lastResult ?? { ok: false, error: timeoutError() } };
    }

    // The tighter of the two bounds, not just `remainingBeforeRequestMs` on its own -- passing
    // that alone would *replace* the client's own configured `timeoutMs` rather than cap it
    // (PlatformApiClient.performOnce() does `options.timeoutMs ?? this.timeoutMs`, so a caller
    // option always wins outright), which could silently loosen a deliberately short client
    // timeout on every poll request whenever the remaining poll budget is larger.
    const result = await getScenarioSession(client, scenarioSessionId, {
      signal,
      timeoutMs: Math.min(client.timeoutMs, remainingBeforeRequestMs),
    });
    lastResult = result;

    if (!result.ok) {
      if (result.error.type === "aborted") {
        return { reason: "aborted", result };
      }
      // Any individual request timeout stops the whole poll and is reported as a polling
      // timeout, not a generic API error -- whether it was cut off by the remaining poll budget
      // or by the client's own (possibly shorter) `timeoutMs`. `maxDurationMs` is an upper bound
      // on total poll duration, not a per-request retry budget: e.g. with the defaults, a slow
      // GET can time out at 10s (client.timeoutMs) even with ~50s of `maxDurationMs` still left,
      // and this intentionally ends the entire poll rather than retrying the request.
      return { reason: result.error.type === "timeout" ? "timeout" : "error", result };
    }
    if (SCENARIO_SESSION_STATUS_STOPS_POLLING[result.value.status]) {
      return { reason: "session_status", result };
    }

    const elapsedMs = Date.now() - startedAt;
    if (elapsedMs >= maxDurationMs) {
      return { reason: "timeout", result };
    }

    const aborted = await _sleep(Math.min(intervalMs, maxDurationMs - elapsedMs), signal);
    if (aborted) {
      return { reason: "aborted", result: { ok: false, error: abortedError() } };
    }
  }
}

function _sleep(ms: number, signal: AbortSignal | undefined): Promise<boolean> {
  if (ms <= 0 || signal?.aborted) {
    return Promise.resolve(signal?.aborted ?? false);
  }
  return new Promise((resolve) => {
    const onAbort = () => {
      clearTimeout(timer);
      resolve(true);
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve(false);
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}
