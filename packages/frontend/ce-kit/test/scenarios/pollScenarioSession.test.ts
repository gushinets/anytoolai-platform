import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { pollScenarioSession } from "../../src/scenarios/pollScenarioSession";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

function sessionPayload(status: string): unknown {
  return {
    scenario_session_id: "scenario_session_123",
    job_id: "job_123",
    status,
    current_checkpoint_id: null,
    allowed_next_actions: [],
    result_artifact_id: null,
  };
}

/** Advances fake timers in small ticks so pending microtasks (fetch/promise chains) settle. */
async function advance(ms: number, step = 50): Promise<void> {
  for (let elapsed = 0; elapsed < ms; elapsed += step) {
    await vi.advanceTimersByTimeAsync(Math.min(step, ms - elapsed));
  }
}

describe("pollScenarioSession", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("stops immediately on a terminal status without waiting", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, sessionPayload("completed")));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await pollScenarioSession(client, "scenario_session_123");

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(result.reason).toBe("session_status");
    expect(result.result.ok && result.result.value.status).toBe("completed");
  });

  it("stops on waiting_for_user instead of continuing to poll", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, sessionPayload("waiting_for_user")));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await pollScenarioSession(client, "scenario_session_123");

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(result.reason).toBe("session_status");
  });

  it("polls again on a non-terminal status until it reaches completed", async () => {
    const statuses = ["started", "running", "running", "completed"];
    const fetchImpl = vi.fn(async () => jsonResponse(200, sessionPayload(statuses.shift()!)));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const promise = pollScenarioSession(client, "scenario_session_123", { intervalMs: 1_000 });
    await advance(3_000);
    const result = await promise;

    expect(fetchImpl).toHaveBeenCalledTimes(4);
    expect(result.reason).toBe("session_status");
    expect(result.result.ok && result.result.value.status).toBe("completed");
  });

  it("stops with reason 'error' on a backend error without retrying", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: {
          code: "scenario_session_not_found",
          message: "Scenario session not found.",
          request_id: "req_1",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await pollScenarioSession(client, "unknown_session");

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(result.reason).toBe("error");
    expect(result.result.ok).toBe(false);
  });

  it("stops with reason 'timeout' once maxDurationMs elapses without a terminal status", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, sessionPayload("running")));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const promise = pollScenarioSession(client, "scenario_session_123", {
      intervalMs: 1_000,
      maxDurationMs: 3_000,
    });
    await advance(3_500);
    const result = await promise;

    expect(result.reason).toBe("timeout");
    expect(result.result.ok && result.result.value.status).toBe("running");
  });

  it("stops with reason 'timeout', not 'error', when an in-flight request runs past the polling deadline", async () => {
    // Hangs until its AbortSignal fires, instead of resolving -- simulates a slow/unresponsive
    // backend so the request can only ever settle via the `timeoutMs` bound this poll must put on
    // it. The client's own default per-request timeout (10s) is far longer than `maxDurationMs`
    // below, so without that bound this would run to ~10s instead of stopping at ~3s.
    const fetchImpl = vi.fn((_url: RequestInfo | URL, init?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const promise = pollScenarioSession(client, "scenario_session_123", { maxDurationMs: 3_000 });
    await advance(3_500);
    const result = await promise;

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(result.reason).toBe("timeout");
    expect(result.result).toEqual({ ok: false, error: { type: "timeout" } });
  });

  it("stops with reason 'aborted' when the caller cancels mid-poll", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, sessionPayload("running")));
    const client = makeClient(fetchImpl as unknown as typeof fetch);
    const controller = new AbortController();

    const promise = pollScenarioSession(client, "scenario_session_123", {
      intervalMs: 5_000,
      signal: controller.signal,
    });
    await vi.advanceTimersByTimeAsync(100);
    controller.abort();
    const result = await promise;

    expect(result.reason).toBe("aborted");
    expect(result.result).toEqual({ ok: false, error: { type: "aborted" } });
  });

  it("stops immediately, not after a full interval, if the signal aborts between the poll response and the sleep", async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn(async () => {
      // Simulates the abort landing in the narrow window right after a successful poll
      // response resolves but before the interval sleep starts -- the "abort" event has
      // already fired by the time _sleep() would subscribe to it.
      controller.abort();
      return jsonResponse(200, sessionPayload("running"));
    });
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const promise = pollScenarioSession(client, "scenario_session_123", {
      intervalMs: 10_000,
      signal: controller.signal,
    });
    await vi.advanceTimersByTimeAsync(0);
    const result = await promise;

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(result.reason).toBe("aborted");
    expect(result.result).toEqual({ ok: false, error: { type: "aborted" } });
  });

  it("stops immediately if the signal is already aborted before the first poll", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, sessionPayload("running")));
    const client = makeClient(fetchImpl as unknown as typeof fetch);
    const controller = new AbortController();
    controller.abort();

    const result = await pollScenarioSession(client, "scenario_session_123", {
      signal: controller.signal,
    });

    expect(fetchImpl).not.toHaveBeenCalled();
    expect(result.reason).toBe("aborted");
  });

  it("never starts, replays, or configures workflow execution -- it only ever issues GET requests", async () => {
    const statuses = ["running", "completed"];
    const fetchImpl = vi.fn(async () => jsonResponse(200, sessionPayload(statuses.shift()!)));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const promise = pollScenarioSession(client, "scenario_session_123", { intervalMs: 500 });
    await advance(500);
    await promise;

    for (const [, init] of fetchImpl.mock.calls as unknown as [string, RequestInit][]) {
      expect(init.method).toBe("GET");
    }
  });
});
