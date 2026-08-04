import type { PlatformApiClient, PlatformApiResult } from "../api/client";
import { abortedError } from "../api/errors";
import { getScenarioSession } from "./getScenarioSession";
import type { ScenarioSession } from "./types";

/**
 * Statuses that stop polling. `waiting_for_user` stops here too (not just the workflow-terminal
 * statuses) because it means the frontend must call `nextAction()` next -- continuing to poll
 * would just idle until `maxDurationMs`. See docs/architecture/scenario-session-model.md.
 */
const POLL_STOP_STATUSES: ReadonlySet<string> = new Set([
  "completed",
  "failed",
  "expired",
  "waiting_for_user",
]);

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

  for (;;) {
    if (signal?.aborted) {
      return { reason: "aborted", result: { ok: false, error: abortedError() } };
    }

    const result = await getScenarioSession(client, scenarioSessionId, { signal });

    if (!result.ok) {
      return { reason: result.error.type === "aborted" ? "aborted" : "error", result };
    }
    if (POLL_STOP_STATUSES.has(result.value.status)) {
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
