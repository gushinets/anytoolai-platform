// Acceptance Builder's own meaning: the two input mappings, the two result shapes, the contract's
// copy composition (structured fields only, never the narrative `document`), and the activation
// rule. Shared runtime behavior is proven in ProductRunPage*.test.tsx. Results are composed from
// the on-disk fake-provider fixtures exactly as the backend bundle composes them.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AcceptanceBuilderProduct, checkDefinition, draftDefinition } from "../src/products/acceptanceBuilder/AcceptanceBuilderProduct";
import { ACCEPTANCE_BUILDER_MESSAGES } from "../src/products/acceptanceBuilder/messages";
import {
  DELTA_CRITERIA,
  DELTA_STATUSES,
  LIST_FIELDS,
  VERDICTS,
  extractCheckResult,
  extractDraftResult,
  hasCriteria,
} from "../src/products/acceptanceBuilder/parseAcceptanceBuilder";
import {
  errorResponse,
  guestIdentityResponse,
  makeClientCapturingRequests,
  makeClientWithDeferredRoute,
  quotaResponse,
  resultResponse,
  routesFor,
  runtimeConfigResponse,
  sessionResponse,
  startResponse,
  type RouteQueues,
} from "./fixtures/platformResponses";
import { ProductRunPage } from "../src/products/runtime/ProductRunPage";
import { AcceptanceBuilderResultView } from "../src/products/acceptanceBuilder/AcceptanceBuilderResult";
import { LOCALE_STORAGE_KEY } from "../src/i18n/localeStorage";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { useAttachSession } from "../src/products/runtime/attachSession";
import { makeRender } from "./support/renderWithI18n";
import type { ProductRunEvent } from "../src/products/runtime/productDefinition";

const render = makeRender(ACCEPTANCE_BUILDER_MESSAGES);
const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURE_ROOT = resolve(HERE, "../../../tests/fixtures/provider/fake_provider_outputs");
const SCHEMA_ROOT = resolve(
  HERE,
  "../../../packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/acceptance_builder/schemas",
);

function fixture(action: string, suffix: string): Record<string, unknown> {
  const text = readFileSync(resolve(FIXTURE_ROOT, `acceptance_builder.${action}_v1${suffix}.json`), "utf8");
  return (JSON.parse(text) as { response_json: Record<string, unknown> }).response_json;
}

type CheckOutputSchema = {
  properties: {
    extracted: { properties: { values: { properties: Record<string, unknown> } } };
    comparison: { properties: { verdict: { enum: string[] }; deltas: { prefixItems: { $ref: string }[] } } };
  };
  $defs: Record<string, { properties: { status: { enum: string[] } } }>;
};
type InputSchema = { properties: { brief_text: { maxLength: number }; deliverable_text?: { maxLength: number } } };
function schema<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(SCHEMA_ROOT, name), "utf8")) as T;
}

type Suffix = "" | ".weak_input";
const draftOutput = (suffix: Suffix = "") => ({
  extracted: fixture("extract", suffix),
  document: fixture("draft_document", suffix),
});
const checkOutput = (suffix: Suffix = "") => ({
  extracted: fixture("extract", suffix),
  comparison: fixture("compare", suffix),
  document: fixture("check_document", suffix),
});

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  window.localStorage.clear();
});

beforeEach(() => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(() => Promise.resolve()) },
  });
});

describe("Acceptance Builder definitions", () => {
  it("maps each mode to its own scenario input", () => {
    expect(draftDefinition.scenarioId).toBe("acceptance_builder.draft_v1");
    expect(draftDefinition.toInput({ briefText: "brief" })).toEqual({ brief_text: "brief" });
    expect(checkDefinition.scenarioId).toBe("acceptance_builder.check_v1");
    expect(checkDefinition.toInput({ briefText: "brief", deliverableText: "work" })).toEqual({
      brief_text: "brief",
      deliverable_text: "work",
    });
  });

  it("copies the schemas' enums, delta order and text length limits (drift guard)", () => {
    const output = schema<CheckOutputSchema>("check_output.schema.json");
    expect([...LIST_FIELDS]).toEqual(Object.keys(output.properties.extracted.properties.values.properties));
    const { comparison } = output.properties;
    expect([...VERDICTS]).toEqual(comparison.properties.verdict.enum);
    expect(DELTA_CRITERIA.map((id) => `#/$defs/delta_${id}`)).toEqual(
      comparison.properties.deltas.prefixItems.map((item) => item.$ref),
    );
    for (const id of DELTA_CRITERIA) {
      expect([...DELTA_STATUSES]).toEqual(output.$defs[`delta_${id}`].properties.status.enum);
    }
    const draftMax = schema<InputSchema>("draft_input.schema.json").properties.brief_text.maxLength;
    const checkProps = schema<InputSchema>("check_input.schema.json").properties;
    expect(checkProps.brief_text.maxLength).toBe(draftMax);
    expect(checkProps.deliverable_text?.maxLength).toBe(draftMax);

    const validate = (text: string) => draftDefinition.validate({ briefText: text }).briefText;
    expect(validate("a".repeat(draftMax))).toBeUndefined();
    expect(validate("a".repeat(draftMax + 1))).toEqual({ code: "max_length", maxLength: draftMax });
    expect(validate("  ")).toEqual({ code: "required" });
  });

  it("trims pasted outer whitespace instead of rejecting it, and sends the trimmed text", () => {
    expect(draftDefinition.validate({ briefText: "Brief text\n" })).toEqual({});
    expect(draftDefinition.toInput({ briefText: "\n Brief text \n" })).toEqual({ brief_text: "Brief text" });
    expect(checkDefinition.toInput({ briefText: "a\n", deliverableText: "\tb" })).toEqual({
      brief_text: "a",
      deliverable_text: "b",
    });
  });

  it("requires both texts in check mode", () => {
    expect(Object.keys(checkDefinition.validate({ briefText: "", deliverableText: "" })).sort()).toEqual([
      "briefText",
      "deliverableText",
    ]);
    expect(checkDefinition.validate({ briefText: "a", deliverableText: "b" })).toEqual({});
  });
});

describe("Acceptance Builder result parsing", () => {
  it("accepts the happy and weak-input fixtures", () => {
    expect(extractDraftResult(draftOutput())?.lists.acceptance_criteria).toHaveLength(3);
    const weak = extractCheckResult(checkOutput(".weak_input"));
    expect(weak?.missingFields).toEqual(["acceptance_criteria", "assumptions"]);
    expect(weak?.comparison?.verdict).toBe("does_not_meet");
    expect(weak?.lists.acceptance_criteria).toBeUndefined();
  });

  it("requires a comparison for check and none for draft", () => {
    const { comparison: _omitted, ...withoutComparison } = checkOutput();
    expect(extractCheckResult(withoutComparison)).toBeNull();
    expect(extractDraftResult(checkOutput())).toBeNull();
    expect(extractCheckResult(checkOutput())?.comparison?.verdict).toBe("partially_meets");
  });

  it("rejects an empty list, an unknown list key, out-of-order deltas and an unknown verdict", () => {
    const base = draftOutput();
    const extracted = base.extracted as { values: Record<string, unknown> };
    expect(extractDraftResult({ ...base, extracted: { ...extracted, values: { ...extracted.values, assumptions: [] } } })).toBeNull();
    expect(extractDraftResult({ ...base, extracted: { ...extracted, values: { ...extracted.values, risks: ["x"] } } })).toBeNull();

    const check = checkOutput();
    const comparison = check.comparison as { deltas: unknown[] };
    expect(extractCheckResult({ ...check, comparison: { ...comparison, deltas: [...comparison.deltas].reverse() } })).toBeNull();
    expect(extractCheckResult({ ...check, comparison: { ...comparison, verdict: "great" } })).toBeNull();
  });

  it("counts a draft as viewed only when it lists criteria", () => {
    expect(hasCriteria(extractDraftResult(draftOutput())!)).toBe(true);
    expect(hasCriteria(extractDraftResult(draftOutput(".weak_input"))!)).toBe(false);
  });
});

const IDS = { draft: { productId: "acceptance_builder", scenarioId: "acceptance_builder.draft_v1" }, check: { productId: "acceptance_builder", scenarioId: "acceptance_builder.check_v1" } } as const;

function routes(mode: "draft" | "check", output: Record<string, unknown>): RouteQueues {
  const r = routesFor(IDS[mode]);
  return {
    [r.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS[mode])],
    [r.GUEST_IDENTITY]: [guestIdentityResponse()],
    [r.QUOTA]: [quotaResponse(IDS[mode])],
    [r.START]: [startResponse()],
    [r.SESSION]: [sessionResponse()],
    [r.RESULT]: [resultResponse(IDS[mode], { output })],
    [r.NEXT_ACTION]: [sessionResponse({ status: "completed" })],
  };
}

/** `routes()` for a page that boots twice (a mode switch remounts it) with both scenarios in the config. */
function bothModesRoutes(output: Record<string, unknown>): RouteQueues {
  const r = routesFor(IDS.draft);
  const scenario = (ids: { productId: string; scenarioId: string }) => ({
    scenario_id: ids.scenarioId,
    version: 1,
    allowed_next_actions: ["copy_result"],
    input_renderer_hint: { renderer: "json_schema", schema_ref: `${ids.productId}.input_v1`, schema_version: 1 },
    output_renderer_hint: { renderer: "json_schema", schema_ref: `${ids.productId}.output_v1`, schema_version: 1 },
  });
  return {
    ...routes("draft", output),
    [r.RUNTIME_CONFIG]: [
      runtimeConfigResponse(IDS.draft, {
        scenario_ids: [IDS.draft.scenarioId, IDS.check.scenarioId],
        scenarios: [scenario(IDS.draft), scenario(IDS.check)],
      }),
    ],
    [r.GUEST_IDENTITY]: [guestIdentityResponse(), guestIdentityResponse(), guestIdentityResponse()],
    [r.QUOTA]: [quotaResponse(IDS.draft), quotaResponse(IDS.draft), quotaResponse(IDS.draft)],
  };
}

function resultText(): string {
  const paragraphs = document.querySelectorAll("main p, div p");
  return Array.from(paragraphs).map((p) => p.textContent ?? "").join("\n");
}

// Each mode is a `ProductRunPage` over its own definition; the mode switch itself is covered below.
async function run(mode: "draft" | "check", output: Record<string, unknown>, events: ProductRunEvent[] = []) {
  const made = makeClientCapturingRequests(routes(mode, output));
  const onEvent = (e: ProductRunEvent) => events.push(e);
  render(
    mode === "draft" ? (
      <ProductRunPage definition={draftDefinition} client={made.client} onEvent={onEvent} />
    ) : (
      <ProductRunPage definition={checkDefinition} client={made.client} onEvent={onEvent} />
    ),
  );
  await waitFor(() => expect(screen.getByLabelText("Client brief")).toBeTruthy());
  if (mode === "check") {
    fireEvent.change(screen.getByLabelText("Finished work"), { target: { value: "We delivered it." } });
  }
  fireEvent.change(screen.getByLabelText("Client brief"), { target: { value: "Issue certificates." } });
  fireEvent.click(screen.getByRole("button", { name: mode === "draft" ? "Draft criteria" : "Check deliverable" }));
  return made;
}

describe("Acceptance Builder page", () => {
  it("draft: shows the structured copy text, copies exactly it, and never the narrative", async () => {
    const events: ProductRunEvent[] = [];
    const { calls } = await run("draft", draftOutput(), events);
    await waitFor(() => expect(screen.getByText("Acceptance criteria")).toBeTruthy());

    const expected = [
      "Acceptance criteria\n- A student who finishes a course automatically receives a PDF certificate\n- The certificate is issued for every existing course\n- The certificate uses the brand colors",
      "Assumptions\n- Course completion data already exists in the database",
      "Deliverables\n- Certificate template in brand colors\n- Automated PDF generation service\n- Email that delivers the certificate",
      "Open gaps\nThe brief states all three lists.",
    ].join("\n\n");
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expected));
    await waitFor(() => expect(calls.some((c) => c.key.endsWith("/next-actions/copy_result"))).toBe(true));

    const narrative = (draftOutput().document as { summary: string }).summary;
    expect(expected).not.toContain(narrative);
    await waitFor(() => expect(events.find((e) => e.type === "scenario_completed")).toMatchObject({ resultViewed: true }));
  });

  it("check: leads with the verdict, states its scope and copies verdict lines from the deltas", async () => {
    await run("check", checkOutput());
    await waitFor(() => expect(screen.getAllByText(/judged on four general review criteria/i).length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = (navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(copied.startsWith("Verdict\nVerdict: partially meets expectations.\nScope coverage: partial. ")).toBe(true);
    expect(copied).toContain("\nRequirement fit: match. ");
    expect(copied).toContain("\n\nAcceptance criteria\n- ");
  });

  it("weak input: renders the documented gaps instead of an error, and does not count a draft as viewed", async () => {
    const events: ProductRunEvent[] = [];
    await run("draft", draftOutput(".weak_input"), events);
    await waitFor(() => expect(screen.getAllByText(/Open gaps/).length).toBeGreaterThan(0));
    expect(screen.getAllByText(/Not specified in the brief\./).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/- acceptance criteria: the client should confirm it\./).length).toBeGreaterThan(0);
    await waitFor(() => expect(events.find((e) => e.type === "scenario_completed")).toMatchObject({ resultViewed: false }));
    expect(resultText()).not.toMatch(/went wrong/i);
  });

  it("keeps the contract's English copy text whatever the UI locale", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "fr");
    const result = extractDraftResult(draftOutput())!;
    render(<AcceptanceBuilderResultView result={result} onCopy={() => Promise.resolve(true)} />);
    expect(document.body.textContent).toContain("Acceptance criteria\n- A student");
    expect(document.body.textContent).toContain("Open gaps\nThe brief states all three lists.");
    expect(screen.getByText(/Récapitulatif/)).toBeTruthy();
  });

  it("attaches once: a mode round trip does not re-poll or re-report the handoff session", async () => {
    const events: ProductRunEvent[] = [];
    const base = routes("draft", draftOutput());
    const r = routesFor(IDS.draft);
    // Each remount boots again: give the boot routes a second response.
    const made = makeClientCapturingRequests({
      ...base,
      [r.RUNTIME_CONFIG]: [
        runtimeConfigResponse(IDS.draft, { scenario_ids: [IDS.draft.scenarioId, IDS.check.scenarioId], scenarios: [IDS.draft, IDS.check].map((ids) => ({
          scenario_id: ids.scenarioId,
          version: 1,
          allowed_next_actions: ["copy_result"],
          input_renderer_hint: { renderer: "json_schema", schema_ref: `${ids.productId}.input_v1`, schema_version: 1 },
          output_renderer_hint: { renderer: "json_schema", schema_ref: `${ids.productId}.output_v1`, schema_version: 1 },
        })) }),
      ],
      [r.GUEST_IDENTITY]: [guestIdentityResponse(), guestIdentityResponse(), guestIdentityResponse()],
      [r.QUOTA]: [quotaResponse(IDS.draft), quotaResponse(IDS.draft), quotaResponse(IDS.draft)],
    });
    const ended = vi.fn();
    render(<AcceptanceBuilderProduct client={made.client} attachSessionId="session_1" onEvent={(e) => events.push(e)} onAttachEnd={ended} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "New task" })).toBeTruthy());

    fireEvent.click(screen.getByRole("radio", { name: "Check deliverable" }));
    await waitFor(() => expect(screen.getByLabelText("Finished work")).toBeTruthy());
    fireEvent.click(screen.getByRole("radio", { name: "Draft criteria" }));
    await waitFor(() => expect(screen.getByLabelText("Client brief")).toBeTruthy());

    expect(screen.queryByRole("button", { name: "New task" })).toBeNull();
    // Leaving the attached result is reported once, so the route stops restoring it on reload.
    expect(ended).toHaveBeenCalledTimes(1);
    expect(made.calls.filter((c) => c.key === "GET /v1/scenario-sessions/session_1")).toHaveLength(1);
    expect(events.filter((e) => e.type === "scenario_completed")).toHaveLength(1);
  });

  it("keeps the mode switch blocked when the attached session's poll fails ambiguously, and Try again finishes the same session", async () => {
    const r = routesFor(IDS.draft);
    const made = makeClientCapturingRequests({
      ...routes("draft", draftOutput()),
      [r.SESSION]: [errorResponse(500, "internal_error"), sessionResponse()],
    });
    render(<AcceptanceBuilderProduct client={made.client} attachSessionId="session_1" />);
    await waitFor(() => expect(screen.getByRole("button", { name: /try again/i })).toBeTruthy());
    expect((screen.getByRole("radio", { name: "Check deliverable" }) as HTMLInputElement).disabled).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: "New task" })).toBeTruthy());
    expect((screen.getByRole("radio", { name: "Check deliverable" }) as HTMLInputElement).disabled).toBe(false);
    expect(made.calls.filter((c) => c.key === "GET /v1/scenario-sessions/session_1")).toHaveLength(2);
    expect(made.calls.some((c) => c.key.endsWith("/start"))).toBe(false);
  });

  it.each([
    ["throws synchronously", () => { throw new Error("handler broke"); }],
    ["rejects asynchronously", () => Promise.reject(new Error("handler broke")) as unknown as void],
  ])("still switches mode when the event handler %s", async (_name, handler) => {
    const made = makeClientCapturingRequests(bothModesRoutes(draftOutput()));
    render(<AcceptanceBuilderProduct client={made.client} attachSessionId="session_1" onEvent={handler} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "New task" })).toBeTruthy());

    fireEvent.click(screen.getByRole("radio", { name: "Check deliverable" }));
    await waitFor(() => expect(screen.getByLabelText("Finished work")).toBeTruthy());
  });

  it("keeps the mode switch locked while the attached session is still booting, and releases it once it started", async () => {
    const r = routesFor(IDS.draft);
    const { client, resolveDeferred } = makeClientWithDeferredRoute(routes("draft", draftOutput()), r.RUNTIME_CONFIG);
    render(<AcceptanceBuilderProduct client={client} attachSessionId="session_1" />);

    // Runtime config / identity still loading: the paid-for session has not started polling yet.
    const checkMode = screen.getByRole("radio", { name: "Check deliverable" }) as HTMLInputElement;
    expect(checkMode.disabled).toBe(true);

    resolveDeferred(runtimeConfigResponse(IDS.draft));
    await waitFor(() => expect(screen.getByRole("button", { name: "New task" })).toBeTruthy());
    expect(checkMode.disabled).toBe(false);
  });

  /** The route's real wiring: `useAttachSession` persists the id per tab and its callbacks forget it. */
  function Harness({ client }: { client: PlatformApiClient }) {
    const attach = useAttachSession("acceptance_builder", "session_1");
    return <AcceptanceBuilderProduct client={client} {...attach} />;
  }
  const PERSISTED = "anytoolai.attach_session.acceptance_builder";

  it("releases the lock when the boot of an attached session fails, and keeps the persisted session (a reload retries it)", async () => {
    const r = routesFor(IDS.draft);
    const { client, resolveDeferred } = makeClientWithDeferredRoute(bothModesRoutes(draftOutput()), r.RUNTIME_CONFIG);
    render(<Harness client={client} />);
    const checkMode = screen.getByRole("radio", { name: "Check deliverable" }) as HTMLInputElement;
    expect(checkMode.disabled).toBe(true); // booting
    expect(window.sessionStorage.getItem(PERSISTED)).toBe("session_1");

    resolveDeferred(errorResponse(500, "internal_error"));
    await waitFor(() => expect(screen.getByText(/unavailable right now/i)).toBeTruthy());
    expect(checkMode.disabled).toBe(false); // nothing is running: not locked for good

    fireEvent.click(checkMode);
    // The attach never began, so nothing forgot the paid-for session: a reload still has it.
    expect(window.sessionStorage.getItem(PERSISTED)).toBe("session_1");
  });

  it("forgets the persisted session when own work's result replaces the attached one on screen (not at submit)", async () => {
    const r = routesFor(IDS.draft);
    const output = draftOutput();
    const made = makeClientCapturingRequests({
      ...bothModesRoutes(output),
      [r.START]: [startResponse()],
      [r.SESSION]: [sessionResponse(), sessionResponse()],
      [r.RESULT]: [resultResponse(IDS.draft, { output }), resultResponse(IDS.draft, { output })],
    });
    render(<Harness client={made.client} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "New task" })).toBeTruthy());
    expect(window.sessionStorage.getItem(PERSISTED)).toBe("session_1");

    // Typing alone leaves it (the attached result is still on screen) ...
    fireEvent.change(screen.getByLabelText("Client brief"), { target: { value: "My own brief." } });
    expect(window.sessionStorage.getItem(PERSISTED)).toBe("session_1");
    // ... and so does starting the run: it is forgotten once the own result replaced the attached one.
    fireEvent.click(screen.getByRole("button", { name: /Draft criteria/ }));
    await waitFor(() => expect(window.sessionStorage.getItem(PERSISTED)).toBeNull());
  });

  it("forgets the persisted session on a mode switch only once the attached result was shown", async () => {
    const made = makeClientCapturingRequests(bothModesRoutes(draftOutput()));
    render(<Harness client={made.client} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "New task" })).toBeTruthy());
    expect(window.sessionStorage.getItem(PERSISTED)).toBe("session_1");

    fireEvent.click(screen.getByRole("radio", { name: "Check deliverable" }));
    await waitFor(() => expect(screen.getByLabelText("Finished work")).toBeTruthy());
    expect(window.sessionStorage.getItem(PERSISTED)).toBeNull();
  });

  it("does not show an attached check session as a draft result", async () => {
    const made = makeClientCapturingRequests(routes("draft", checkOutput()));
    render(<AcceptanceBuilderProduct client={made.client} attachSessionId="session_1" />);
    await waitFor(() => expect(screen.getByText(/went wrong drafting/i)).toBeTruthy());
  });

  it("forwards an attached session to the draft mode only", async () => {
    const made = makeClientCapturingRequests({
      ...routes("draft", draftOutput()),
    });
    render(<AcceptanceBuilderProduct client={made.client} attachSessionId="session_1" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "New task" })).toBeTruthy());
    expect(made.calls.some((c) => c.key.endsWith("/start"))).toBe(false);
    expect(made.calls.filter((c) => c.key === "GET /v1/scenario-sessions/session_1")).toHaveLength(1);
  });

  it("switches mode, and disables the switch while a run is active", async () => {
    const made = makeClientCapturingRequests(routes("draft", draftOutput()));
    render(<AcceptanceBuilderProduct client={made.client} />);
    await waitFor(() => expect(screen.getByLabelText("Client brief")).toBeTruthy());
    expect(screen.queryByLabelText("Finished work")).toBeNull();

    fireEvent.change(screen.getByLabelText("Client brief"), { target: { value: "Issue certificates." } });
    fireEvent.click(screen.getByRole("button", { name: "Draft criteria" }));
    const checkMode = screen.getByRole("radio", { name: "Check deliverable" }) as HTMLInputElement;
    await waitFor(() => expect(checkMode.disabled).toBe(true));
    await waitFor(() => expect(screen.getByRole("button", { name: "New task" })).toBeTruthy());
    expect(checkMode.disabled).toBe(false);
  });
});
