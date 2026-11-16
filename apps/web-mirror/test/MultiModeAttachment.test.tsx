import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { ClientUpdateWriterProduct } from "../src/products/clientUpdateWriter/ClientUpdateWriterProduct";
import { CLIENT_UPDATE_WRITER_MESSAGES } from "../src/products/clientUpdateWriter/messages";
import { AcceptanceBuilderProduct } from "../src/products/acceptanceBuilder/AcceptanceBuilderProduct";
import { ACCEPTANCE_BUILDER_MESSAGES } from "../src/products/acceptanceBuilder/messages";
import { readAttachSessionId, rememberAttachSession, useAttachSession } from "../src/products/runtime/attachSession";
import { makeRender } from "./support/renderWithI18n";
import { errorResponse, guestIdentityResponse, jsonResponse, makeClientCapturingRequests, quotaResponse,
  resultResponse, routesFor, runtimeConfigResponse, sessionResponse } from "./fixtures/platformResponses";

function fixture(action: string): Record<string, unknown> {
  const path = resolve(dirname(fileURLToPath(import.meta.url)), "../../../tests/fixtures/provider/fake_provider_outputs", `acceptance_builder.${action}_v1.json`);
  return (JSON.parse(readFileSync(path, "utf8")) as { response_json: Record<string, unknown> }).response_json;
}

const products = [
  {
    productId: "client_update_writer", Component: ClientUpdateWriterProduct, messages: CLIENT_UPDATE_WRITER_MESSAGES,
    modes: [
      { id: "update", label: "Update", field: "Progress notes" },
      { id: "reply_draft", label: "Reply Draft", field: "Client message" },
      { id: "prepaid_request", label: "Prepaid Request", field: "Billing notes" },
    ],
    output: { text: "Original saved result." },
  },
  {
    productId: "acceptance_builder", Component: AcceptanceBuilderProduct, messages: ACCEPTANCE_BUILDER_MESSAGES,
    modes: [
      { id: "draft", label: "Draft criteria", field: "Client brief" },
      { id: "check", label: "Check deliverable", field: "Finished work" },
    ],
    output: { extracted: fixture("extract"), document: fixture("draft_document") },
  },
];

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe.each(products)("$productId attachment recovery", (product) => {
  const { Component, productId, modes } = product;
  const render = makeRender(product.messages);
  const ids = { productId, scenarioId: `${productId}.${modes[0].id}_v1` };
  const r = routesFor(ids);

  function Attached({ client, sessionId }: { client: PlatformApiClient; sessionId?: string }) {
    const attach = useAttachSession(productId, sessionId);
    return <Component client={client} {...attach} />;
  }

  function bootRoutes() {
    return {
      [r.RUNTIME_CONFIG]: [runtimeConfigResponse(ids, {
        scenario_ids: modes.map((mode) => `${productId}.${mode.id}_v1`),
        scenarios: modes.map((mode) => ({
          scenario_id: `${productId}.${mode.id}_v1`, version: 1, allowed_next_actions: ["copy_result"],
          input_renderer_hint: { renderer: "json_schema", schema_ref: `${productId}.input_v1`, schema_version: 1 },
          output_renderer_hint: { renderer: "json_schema", schema_ref: `${productId}.output_v1`, schema_version: 1 },
        })),
      })],
      [r.GUEST_IDENTITY]: [guestIdentityResponse()],
      [r.QUOTA]: Array.from({ length: 8 }, () => quotaResponse(ids, { used_count: 1, remaining_count: 2 })),
      [r.RESULT]: [resultResponse(ids, { output: product.output })],
    };
  }

  it.each(["404", "foreign", "unsupported", "legacy"].flatMap((failure) => [false, true].map((stored) => ({ failure, stored }))))(
    "$failure → explicit New task → all modes and reload (stored=$stored), without a start", async ({ failure, stored }) => {
      const made = makeClientCapturingRequests({
        ...bootRoutes(),
        [r.SESSION]: failure === "legacy" ? [sessionResponse(), sessionResponse()] :
          [failure === "404" ? errorResponse(404, "scenario_session_not_found") :
            sessionResponse({ scenario_id: failure === "foreign" ? "proposal_ai.generate_v1" : `${productId}.future_v1` })],
      });
      if (stored) rememberAttachSession(productId, "session_1", "2026-10-01T10:00:00Z");
      const view = render(<Attached client={made.client} sessionId={stored ? undefined : "session_1"} />);
      await screen.findByRole("button", { name: "New task" });
      if (failure === "legacy") {
        fireEvent.click(screen.getByRole("button", { name: "Try again" }));
        await screen.findByRole("button", { name: "Try again" });
        expect(made.calls.filter((call) => call.key === r.SESSION)).toHaveLength(2);
      } else {
        expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
      }
      expect(readAttachSessionId(productId)).toBe(stored ? "session_1" : undefined);
      expect(screen.queryByRole("form")).toBeNull();
      expect(screen.getAllByRole("radio").every((node) => (node as HTMLInputElement).disabled)).toBe(true);
      fireEvent.click(screen.getByRole("button", { name: "New task" }));
      await screen.findByLabelText(modes[0].field);
      await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("radio", { name: modes[0].label })));
      expect(readAttachSessionId(productId)).toBeUndefined();
      for (const mode of modes.slice(1)) {
        fireEvent.click(screen.getByRole("radio", { name: mode.label }));
        await screen.findByLabelText(mode.field);
      }
      view.unmount();
      render(<Attached client={made.client} />);
      // Only CUW opts into remembering the selected mode; Acceptance Builder remains opt-out.
      await screen.findByLabelText((productId === "client_update_writer" ? modes.at(-1)! : modes[0]).field);
      expect(made.calls.filter((call) => call.key === r.SESSION)).toHaveLength(failure === "legacy" ? 2 : 1);
      expect(made.calls.some((call) => call.key.endsWith("/start"))).toBe(false);
      expect(screen.getByText(/2 of 3/)).toBeTruthy();
    },
  );

  it.each([
    ["503", () => errorResponse(503, "internal_error")],
    ["401", () => errorResponse(401, "unauthorized")],
    ["403", () => errorResponse(403, "forbidden")],
    ["429", () => errorResponse(429, "rate_limited")],
    ["missing identity", () => sessionResponse()],
    ["malformed 404", () => jsonResponse(404, { unexpected: true })],
    ["network failure", () => { throw new TypeError("Network unavailable"); }],
    ["timeout", undefined],
  ])("preserves %s for retry of the same session and restores its original result", async (_label, failure) => {
    const made = makeClientCapturingRequests({
      ...bootRoutes(),
      [r.SESSION]: [...(failure ? [failure] : []), ...Array.from({ length: 2 }, () => sessionResponse({ scenario_id: ids.scenarioId }))],
    });
    if (!failure) vi.spyOn(made.client, "request").mockResolvedValueOnce({ ok: false, error: { type: "timeout" } });
    render(<Attached client={made.client} sessionId="session_1" />);
    const retry = await screen.findByRole("button", { name: "Try again" });
    expect(readAttachSessionId(productId)).toBeUndefined();
    expect(screen.queryByRole("button", { name: "New task" }) !== null).toBe(_label === "missing identity");
    fireEvent.click(retry);
    await screen.findByRole("button", { name: "Copy" });
    expect(readAttachSessionId(productId)).toBe("session_1");
    expect(screen.getByRole("button", { name: "Copy" })).toBeTruthy();
    expect(made.calls.filter((call) => call.key === r.SESSION)).toHaveLength(failure ? 3 : 2);
    expect(made.calls.filter((call) => call.key === r.RESULT)).toHaveLength(1);
    expect(made.calls.some((call) => call.key.endsWith("/start"))).toBe(false);
    expect(screen.getByText(/2 of 3/)).toBeTruthy();
  });

  it.each(["404", "legacy"])("a newer accepted session survives discarding an older %s attachment, then reload restores it", async (failure) => {
    const made = makeClientCapturingRequests({
      ...bootRoutes(),
      [r.SESSION]: [failure === "legacy" ? sessionResponse() : errorResponse(404, "scenario_session_not_found")],
      "GET /v1/scenario-sessions/newer": Array.from({ length: 2 }, () => sessionResponse({
        scenario_session_id: "newer", scenario_id: ids.scenarioId,
      })),
      [r.RESULT]: [resultResponse(ids, { scenario_session_id: "newer", output: product.output })],
    });
    const view = render(<Attached client={made.client} sessionId="session_1" />);
    const exit = await screen.findByRole("button", { name: "New task" });
    rememberAttachSession(productId, "newer", "2026-10-01T10:05:00Z");
    fireEvent.click(exit);
    await screen.findByLabelText(modes[0].field);
    expect(readAttachSessionId(productId)).toBe("newer");
    view.unmount();
    render(<Attached client={made.client} />);
    await screen.findByRole("button", { name: "Copy" });
    expect(readAttachSessionId(productId)).toBe("newer");
    expect(made.calls.some((call) => call.key.endsWith("/start"))).toBe(false);
  });
});
