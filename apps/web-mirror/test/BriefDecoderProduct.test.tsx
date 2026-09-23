// Brief Decoder's own meaning: the brief_text mapping, the four-part composite result, the
// contract's copy composition, and the activation rule (`web.result_viewed` only for a non-empty
// question list). Shared runtime behavior is proven once in ProductRunPage.test.tsx. Results are
// composed from the on-disk fake-provider fixtures exactly as the backend bundle test composes them.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { briefDecoderDefinition } from "../src/products/briefDecoder/BriefDecoderProduct";
import { composeCopyText, extractBriefDecoderResult } from "../src/products/briefDecoder/briefDecoderResult";
import { BRIEF_DECODER_MESSAGES } from "../src/products/briefDecoder/messages";
import { ProductRunPage } from "../src/products/runtime/ProductRunPage";
import type { ProductRunEvent } from "../src/products/runtime/productDefinition";
import {
  errorResponse,
  guestIdentityResponse,
  makeClient,
  quotaResponse,
  resultResponse,
  routesFor,
  runtimeConfigResponse,
  sessionResponse,
  startResponse,
} from "./fixtures/platformResponses";
import { makeRender } from "./support/renderWithI18n";

const render = makeRender(BRIEF_DECODER_MESSAGES);
const IDS = { productId: "brief_decoder", scenarioId: "brief_decoder.decode_v1" } as const;
const ROUTES = routesFor(IDS);
const FIXTURE_ROOT = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../tests/fixtures/provider/fake_provider_outputs",
);

function fixture(action: string, suffix: string): Record<string, unknown> {
  const text = readFileSync(resolve(FIXTURE_ROOT, `brief_decoder.${action}_v1${suffix}.json`), "utf8");
  return (JSON.parse(text) as { response_json: Record<string, unknown> }).response_json;
}

/** The composed workflow output: brief = A01 whole, issues = A04's, questions = A05's, document =
 * A10. A05 is skipped for `.no_issues` (no question fixture exists), so questions is empty there. */
function composedOutput(suffix: "" | ".weak_input" | ".no_issues"): Record<string, unknown> {
  return {
    brief: fixture("extract_brief", suffix),
    issues: (fixture("detect_issues", suffix) as { issues: unknown[] }).issues,
    questions: suffix === ".no_issues" ? [] : (fixture("generate_questions", suffix) as { questions: unknown[] }).questions,
    document: fixture("generate_summary", suffix),
  };
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

beforeEach(() => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(() => Promise.resolve()) },
  });
});

function routes(output: Record<string, unknown>) {
  return {
    [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
    [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
    [ROUTES.QUOTA]: [quotaResponse(IDS)],
    [ROUTES.START]: [startResponse()],
    [ROUTES.SESSION]: [sessionResponse()],
    [ROUTES.RESULT]: [resultResponse(IDS, { output })],
    [ROUTES.NEXT_ACTION]: [sessionResponse({ status: "completed" })],
  };
}

async function decode(queues: ReturnType<typeof routes>, events: ProductRunEvent[] = []) {
  const made = makeClient(queues);
  render(<ProductRunPage definition={briefDecoderDefinition} client={made.client} onEvent={(e) => events.push(e)} />);
  await waitFor(() => expect(screen.getByLabelText("Client brief")).toBeTruthy());
  fireEvent.change(screen.getByLabelText("Client brief"), { target: { value: "Need a website by the holidays." } });
  fireEvent.click(screen.getByRole("button", { name: "Decode brief" }));
  return made;
}

const completedEvents = (events: ProductRunEvent[]) => events.filter((e) => e.type === "scenario_completed");

describe("Brief Decoder definition", () => {
  it("maps the form to brief_text and identifies its scenario", () => {
    expect(briefDecoderDefinition.productId).toBe("brief_decoder");
    expect(briefDecoderDefinition.scenarioId).toBe("brief_decoder.decode_v1");
    expect(briefDecoderDefinition.toInput({ briefText: "abc" })).toEqual({ brief_text: "abc" });
  });

  it("validates like the input schema: required, no outer whitespace, 8000 code points", () => {
    const validate = (briefText: string) => briefDecoderDefinition.validate({ briefText }).briefText;
    expect(validate("")).toBeDefined();
    expect(validate("   ")).toBeDefined();
    expect(validate("brief\n")).toBeDefined();
    expect(validate("a".repeat(8000))).toBeUndefined();
    expect(validate("a".repeat(8001))).toBeDefined();
    expect(validate("😀".repeat(8000))).toBeUndefined();
  });

  it("extracts the composed fixtures and rejects unusable shapes", () => {
    for (const suffix of ["", ".weak_input", ".no_issues"] as const) {
      expect(extractBriefDecoderResult(composedOutput(suffix))).not.toBeNull();
    }
    const good = composedOutput("");
    expect(extractBriefDecoderResult({ ...good, questions: "nope" })).toBeNull();
    expect(extractBriefDecoderResult({ ...good, document: { sections: [] } })).toBeNull();
    expect(extractBriefDecoderResult({ ...good, issues: [{ category: "x", severity: "low", description: "d" }] })).toBeNull();
    expect(extractBriefDecoderResult({ ...good, questions: [{ question: "q", rationale: "r", priority: "urgent" }] })).toBeNull();
    expect(extractBriefDecoderResult({ ...good, brief: { values: {}, missing_fields: ["colour"] } })).toBeNull();
    expect(extractBriefDecoderResult({})).toBeNull();
  });

  it("composes the copy text per renderer_contract.yaml", () => {
    expect(
      composeCopyText({
        sections: [
          { title: "A", content: "one" },
          { title: "B", content: "two" },
        ],
        summary: "done",
      }),
    ).toBe("A\none\n\nB\ntwo\n\ndone");
  });
});

describe("Brief Decoder page", () => {
  it("shows title, description and quota", async () => {
    const { client } = makeClient(routes(composedOutput("")));
    render(<ProductRunPage definition={briefDecoderDefinition} client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Client brief")).toBeTruthy());
    expect(screen.getByRole("heading", { name: "Brief Decoder" })).toBeTruthy();
    expect(screen.getByText(/Turn a client brief into structured details/)).toBeTruthy();
    expect(screen.getByText(/runs? remaining/)).toBeTruthy();
  });

  it("makes no start call for an empty brief", async () => {
    const { client, calls } = makeClient(routes(composedOutput("")));
    render(<ProductRunPage definition={briefDecoderDefinition} client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Client brief")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Decode brief" }));
    expect(await screen.findByText("Client brief: required.")).toBeTruthy();
    expect(calls.some((call) => call.key === ROUTES.START)).toBe(false);
  });

  it("renders the four parts for the happy fixtures, emits one result_viewed, and copies the composed document", async () => {
    const output = composedOutput("");
    const expected = extractBriefDecoderResult(output)!;
    const events: ProductRunEvent[] = [];
    const { calls } = await decode(routes(output), events);

    await waitFor(() => expect(screen.getByRole("heading", { name: /clarifying questions/ })).toBeTruthy());
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "Brief",
      "Issues",
      `${expected.questions.length} clarifying questions`,
      "Summary document",
    ]);
    expect(screen.getAllByRole("listitem").length).toBeGreaterThan(expected.questions.length);
    expect(completedEvents(events)).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(composeCopyText(expected.document));
    const nextAction = calls.filter((call) => call.key === ROUTES.NEXT_ACTION);
    expect(nextAction).toHaveLength(1);
    expect(JSON.parse(nextAction[0].init.body as string)).toEqual({ checkpoint_id: "checkpoint_1" });
  });

  it("renders the weak-input fixtures as a full, activating result", async () => {
    const events: ProductRunEvent[] = [];
    await decode(routes(composedOutput(".weak_input")), events);
    await waitFor(() => expect(screen.getByRole("heading", { name: /clarifying questions/ })).toBeTruthy());
    expect(screen.getByRole("heading", { name: "4 clarifying questions" })).toBeTruthy();
    expect(screen.queryByText("No clarifying questions were generated.")).toBeNull();
    expect(completedEvents(events)).toHaveLength(1);
  });

  it("renders both empty states for no issues, makes no readiness claim, emits no result_viewed, and still copies", async () => {
    const events: ProductRunEvent[] = [];
    await decode(routes(composedOutput(".no_issues")), events);
    await waitFor(() => expect(screen.getByText("No issues found.")).toBeTruthy());
    expect(screen.getByText("No clarifying questions were generated.")).toBeTruthy();
    expect(completedEvents(events)).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
  });

  it("shows the run-failed text and no result when the session fails", async () => {
    const queues = { ...routes(composedOutput("")), [ROUTES.SESSION]: [sessionResponse({ status: "failed" })] };
    await decode(queues);
    expect(await screen.findByText("Something went wrong decoding your brief. Please try again.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
  });

  it("shows quota exhaustion for an authoritative 429", async () => {
    await decode({ ...routes(composedOutput("")), [ROUTES.START]: [errorResponse(429, "quota_exhausted")] });
    expect(await screen.findByText(/used all your/)).toBeTruthy();
  });
});
