import { describe, expect, it } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { isResultNotFound, isResultUnavailable } from "../../src/api/errors/classify";
import { getQuota } from "../../src/quota/getQuota";
import { getResult } from "../../src/results/getResult";
import { getScenarioSession } from "../../src/scenarios/getScenarioSession";
import { pollScenarioSession } from "../../src/scenarios/pollScenarioSession";
import { prepareScenarioStart } from "../../src/scenarios/prepareScenarioStart";
import { createInMemoryAsyncStorage } from "../../src/storage/inMemoryAsyncStorage";
import { createFakePlatformServer } from "./fakePlatformServer";

describe("scenario lifecycle integration (create guest -> quota -> keyed start -> retry -> poll)", () => {
  it("retries the same prepared start with the original session/job and consumes one quota unit", async () => {
    const server = createFakePlatformServer({ quotaLimit: 3, pollsUntilComplete: 2 });
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl: server.fetchImpl });
    const storage = createInMemoryAsyncStorage();

    const identityResult = await client.createGuestIdentity({ storage });
    if (!identityResult.ok) throw new Error("expected guest identity creation to succeed");
    const identity = identityResult.value;
    expect(identity.guestId).toBe("guest_1");

    const initialQuota = await getQuota(client, { productId: "kernel_demo", guestId: identity.guestId });
    expect(initialQuota).toMatchObject({ ok: true, value: { usedCount: 0, remainingCount: 3, exhausted: false } });

    const prepared = prepareScenarioStart({
      productId: "kernel_demo",
      scenarioId: "kernel_demo.single_action_smoke_v1",
      frontendId: "kernel_demo_ce",
      input: { text: "hello" },
      guestId: identity.guestId,
    });

    const firstAttempt = await prepared.execute(client);
    expect(firstAttempt.ok).toBe(true);
    if (!firstAttempt.ok) throw new Error("expected first start attempt to succeed");

    // Simulates a transport-level ambiguous failure being retried explicitly with the same handle.
    const retryAttempt = await prepared.execute(client);
    expect(retryAttempt.ok).toBe(true);
    if (!retryAttempt.ok) throw new Error("expected retry attempt to succeed");

    expect(retryAttempt.value.scenarioSessionId).toBe(firstAttempt.value.scenarioSessionId);
    expect(retryAttempt.value.jobId).toBe(firstAttempt.value.jobId);

    const quotaAfterRetry = await getQuota(client, { productId: "kernel_demo", guestId: identity.guestId });
    expect(quotaAfterRetry).toMatchObject({ ok: true, value: { usedCount: 1, remainingCount: 2 } });
    expect(server.getUsedCount(identity.guestId)).toBe(1);

    // A separate prepared operation (a genuinely new submission) gets a different session and
    // consumes a second quota unit -- proving the dedup above wasn't just "any repeat call".
    const secondScenario = await prepareScenarioStart({
      productId: "kernel_demo",
      scenarioId: "kernel_demo.single_action_smoke_v1",
      frontendId: "kernel_demo_ce",
      input: { text: "hello" },
      guestId: identity.guestId,
    }).execute(client);
    expect(secondScenario.ok).toBe(true);
    if (!secondScenario.ok) throw new Error("expected second start to succeed");
    expect(secondScenario.value.scenarioSessionId).not.toBe(firstAttempt.value.scenarioSessionId);

    const quotaAfterSecond = await getQuota(client, { productId: "kernel_demo", guestId: identity.guestId });
    expect(quotaAfterSecond).toMatchObject({ ok: true, value: { usedCount: 2 } });

    const polled = await pollScenarioSession(client, firstAttempt.value.scenarioSessionId, {
      intervalMs: 1,
      maxDurationMs: 5_000,
    });
    expect(polled.reason).toBe("session_status");
    expect(polled.result.ok && polled.result.value.status).toBe("completed");
    expect(polled.result.ok && polled.result.value.scenarioSessionId).toBe(
      firstAttempt.value.scenarioSessionId,
    );

    const finalSession = await getScenarioSession(client, firstAttempt.value.scenarioSessionId);
    expect(finalSession).toMatchObject({
      ok: true,
      value: {
        status: "completed",
        currentCheckpointId: "result_ready",
        allowedNextActions: ["copy_result"],
      },
    });

    // Polling never mutated quota -- only the two prior scenario starts did.
    const quotaAfterPoll = await getQuota(client, { productId: "kernel_demo", guestId: identity.guestId });
    expect(quotaAfterPoll).toMatchObject({ ok: true, value: { usedCount: 2 } });

    // The terminal snapshot's resultArtifactId feeds straight into getResult() -- CE-kit callers
    // never construct this id themselves.
    const resultArtifactId = polled.result.ok ? polled.result.value.resultArtifactId : null;
    expect(resultArtifactId).not.toBeNull();
    const result = await getResult(client, resultArtifactId as string);
    expect(result).toMatchObject({
      ok: true,
      value: {
        resultArtifactId,
        scenarioSessionId: firstAttempt.value.scenarioSessionId,
        jobId: firstAttempt.value.jobId,
        workflowId: "kernel_demo.single_action_extract_v1",
        output: { title: "Example", fields: ["one", "two"] },
      },
    });
  });

  it("returns safe not_found/unavailable/invalid_response results for the result artifact edge cases", async () => {
    const server = createFakePlatformServer();
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl: server.fetchImpl });

    const notFound = await getResult(client, "artifact_never_existed");
    expect(notFound.ok).toBe(false);
    expect(!notFound.ok && isResultNotFound(notFound.error)).toBe(true);

    const unavailable = await getResult(client, "artifact_unavailable");
    expect(unavailable.ok).toBe(false);
    expect(!unavailable.ok && isResultUnavailable(unavailable.error)).toBe(true);

    const malformed = await getResult(client, "artifact_malformed");
    expect(malformed).toEqual({
      ok: false,
      error: {
        type: "invalid_response",
        status: 200,
        message: "Result artifact response was invalid.",
      },
    });
  });

  it("surfaces 429 quota_exhausted with no fake session/job once quota runs out", async () => {
    const server = createFakePlatformServer({ quotaLimit: 1 });
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl: server.fetchImpl });
    const storage = createInMemoryAsyncStorage();
    const identityResult = await client.createGuestIdentity({ storage });
    if (!identityResult.ok) throw new Error("expected guest identity creation to succeed");
    const identity = identityResult.value;

    const request = {
      productId: "kernel_demo",
      scenarioId: "kernel_demo.single_action_smoke_v1",
      frontendId: "kernel_demo_ce",
      input: { text: "hello" },
      guestId: identity.guestId,
    };

    const first = await prepareScenarioStart(request).execute(client);
    expect(first.ok).toBe(true);

    const second = await prepareScenarioStart(request).execute(client);
    expect(second).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 429,
        code: "quota_exhausted",
        message: "Guest quota exhausted.",
        requestId: "req_quota_exhausted",
      },
    });
    expect(server.getUsedCount(identity.guestId)).toBe(1);
  });
});
