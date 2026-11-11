import { StrictMode, type ComponentType } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ProductMessagesByLocale } from "../src/i18n";
import { ProposalAIProduct } from "../src/products/proposalAi/ProposalAIProduct";
import { PROPOSAL_AI_MESSAGES } from "../src/products/proposalAi/messages";
import { ClientUpdateWriterProduct } from "../src/products/clientUpdateWriter/ClientUpdateWriterProduct";
import { CLIENT_UPDATE_WRITER_MESSAGES } from "../src/products/clientUpdateWriter/messages";
import { useAttachSession, readAttachSessionId, type AttachProps } from "../src/products/runtime/attachSession";
import { readProductDraft } from "../src/products/runtime/draftStorage";
import { makeRender } from "./support/renderWithI18n";
import { errorResponse, guestIdentityResponse, idempotencyKeyOf, makeClient, makeClientWithDeferredCalls, quotaResponse,
  resultResponse, routesFor, runtimeConfigResponse, sessionResponse, startResponse } from "./fixtures/platformResponses";

const cases: Array<{
  productId: string;
  mode: string;
  Component: ComponentType<AttachProps & { client: PlatformApiClient }>;
  messages: ProductMessagesByLocale;
  fields: Array<[string | RegExp, string]>;
  submit: string;
}> = [
  { productId: "proposal_ai", mode: "generate", Component: ProposalAIProduct, messages: PROPOSAL_AI_MESSAGES,
    fields: [[/^Describe the task/, "Build a landing page."], [/^Your experience and strengths/, "Frontend freelancer."]], submit: "Generate proposal" },
  { productId: "client_update_writer", mode: "update", Component: ClientUpdateWriterProduct, messages: CLIENT_UPDATE_WRITER_MESSAGES,
    fields: [["Progress notes", "The first milestone is ready."]], submit: "Write update" },
  { productId: "client_update_writer", mode: "reply_draft", Component: ClientUpdateWriterProduct, messages: CLIENT_UPDATE_WRITER_MESSAGES,
    fields: [["Client message", "Where is the invoice?"], ["Reply goal", "Confirm it was sent."]], submit: "Write reply" },
  { productId: "client_update_writer", mode: "prepaid_request", Component: ClientUpdateWriterProduct, messages: CLIENT_UPDATE_WRITER_MESSAGES,
    fields: [["Billing notes", "The next milestone starts Monday."], ["Amount", "500 USD"]], submit: "Write request" },
];

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
});

describe.each(cases)("$productId/$mode: own start from an attached result", (scenario) => {
  const { productId, mode, Component } = scenario;
  const ids = { productId, scenarioId: `${productId}.${mode}_v1` };
  const r = routesFor(ids);
  const draftKey = `anytoolai.product_draft.${productId}.${mode}`;
  const attachedRoute = "GET /v1/scenario-sessions/attached";
  const render = makeRender(scenario.messages);

  // The real route's owner: the URL is removed, and remount reads only persisted recovery state.
  function Page({ client, sessionId }: { client: PlatformApiClient; sessionId?: string }) {
    const attach = useAttachSession(productId, sessionId);
    return <Component client={client} {...attach} />;
  }

  function queues() {
    return {
      [r.RUNTIME_CONFIG]: [runtimeConfigResponse(ids)],
      [r.GUEST_IDENTITY]: [guestIdentityResponse()],
      [r.QUOTA]: Array.from({ length: 5 }, () => quotaResponse(ids)),
      [attachedRoute]: Array.from({ length: 2 }, () => sessionResponse({
        scenario_session_id: "attached", scenario_id: ids.scenarioId, result_artifact_id: "attached_result",
      })),
      "GET /v1/results/attached_result": [resultResponse(ids, {
        scenario_session_id: "attached", result_artifact_id: "attached_result", output: { text: "Old attached result." },
      })],
      [r.START]: [startResponse()],
      [r.SESSION]: [sessionResponse({ scenario_id: ids.scenarioId })],
      [r.RESULT]: [resultResponse(ids, { output: { text: "New own result." } })],
    };
  }

  async function openAndFill(client: PlatformApiClient) {
    window.history.replaceState(null, "", `/products/${productId}?session=attached`);
    render(<Page client={client} sessionId="attached" />);
    await screen.findByText("Old attached result.");
    expect(window.location.search).toBe("");
    expect(readAttachSessionId(productId)).toBe("attached");
    for (const [label, value] of scenario.fields) fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }

  it.each(["poll", "result"])("reload before own %s completes restores the new session without another start", async (stage) => {
    const deferred = stage === "poll" ? r.SESSION : r.RESULT;
    const first = makeClientWithDeferredCalls(queues(), { [deferred]: 1 });
    await openAndFill(first.client);
    fireEvent.click(screen.getByRole("button", { name: scenario.submit }));
    await waitFor(() => expect(first.calls.filter((call) => call.key === deferred)).toHaveLength(1));
    expect(readProductDraft(draftKey)?.run?.scenarioSessionId).toBe("session_1");
    expect(screen.getByText("Old attached result.")).toBeTruthy();
    cleanup();
    const second = makeClient(queues());
    render(<StrictMode><Page client={second.client} /></StrictMode>);
    try {
      await screen.findByText("New own result.");
      for (const [label, value] of scenario.fields) expect((screen.getByLabelText(label) as HTMLInputElement).value).toBe(value);
      expect(second.calls.filter((call) => call.key === r.SESSION)).toHaveLength(1);
      expect(second.calls.some((call) => call.key === attachedRoute || call.key.endsWith("/start"))).toBe(false);
      expect(first.calls.filter((call) => call.key.endsWith("/start"))).toHaveLength(1);
      fireEvent.click(screen.getByRole("button", { name: "New task" }));
      cleanup();
      const third = makeClient(queues());
      render(<Page client={third.client} />);
      // New task must not resurrect either the replaced attachment or the cleared own run.
      await screen.findByLabelText(scenario.fields[0]![0]);
      expect(third.calls.some((call) => call.key.includes("/scenario-sessions/") || call.key.endsWith("/start"))).toBe(false);
    } finally {
      first.resolveCall(deferred, 0, stage === "poll" ? sessionResponse() : resultResponse(ids));
    }
  });

  it.each(["draft", "selection"])("preserves old recovery when the accepted run's %s write fails", async (failure) => {
    const first = makeClientWithDeferredCalls(queues(), { [r.SESSION]: 1 });
    await openAndFill(first.client);
    const originalSet = Storage.prototype.setItem;
    const blockedKey = failure === "draft" ? draftKey : `anytoolai.attach_session.${productId}`;
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (this: Storage, key, value) {
      if (key === blockedKey) throw new DOMException("Full", "QuotaExceededError");
      originalSet.call(this, key, value);
    });
    try {
      fireEvent.click(screen.getByRole("button", { name: scenario.submit }));
      await waitFor(() => expect(first.calls.filter((call) => call.key === r.SESSION)).toHaveLength(1));
      expect(readAttachSessionId(productId)).toBe("attached");
      expect(screen.getByText("Old attached result.")).toBeTruthy();
      cleanup();
      spy.mockRestore();
      const second = makeClient(queues());
      render(<Page client={second.client} />);
      await screen.findByText("Old attached result.");
      expect(second.calls.some((call) => call.key === r.SESSION || call.key.endsWith("/start"))).toBe(false);
    } finally {
      spy.mockRestore();
      first.resolveCall(r.SESSION, 0, sessionResponse());
    }
  });

  it.each([422, 429, 503])("keeps the old session across reload after a %s start failure", async (status) => {
    const first = makeClient({ ...queues(), [r.START]: Array.from({ length: 2 }, () => errorResponse(status, status === 429 ? "quota_exhausted" : "start_failed")) });
    await openAndFill(first.client);
    fireEvent.click(screen.getByRole("button", { name: scenario.submit }));
    if (status === 429) await screen.findByText(/used all your/);
    else await screen.findByRole("button", { name: "Try again" });
    expect(readAttachSessionId(productId)).toBe("attached");
    expect(readProductDraft(draftKey)?.run).toBeUndefined();
    const starts = first.calls.filter((call) => call.key === r.START);
    expect(starts).toHaveLength(status === 503 ? 2 : 1);
    if (status === 503) expect(idempotencyKeyOf(starts[0]!)).toBe(idempotencyKeyOf(starts[1]!));
    cleanup();
    const second = makeClient(queues());
    render(<Page client={second.client} />);
    await screen.findByText("Old attached result.");
    expect(second.calls.some((call) => call.key === r.SESSION || call.key.endsWith("/start"))).toBe(false);
  });
});
