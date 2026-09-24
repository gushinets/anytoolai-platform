// Brief Decoder's own meaning: the brief_text mapping, the four-part composite result, the
// contract's copy composition, and the activation rule (`web.result_viewed` only for a non-empty
// question list). Shared runtime behavior is proven once in ProductRunPage.test.tsx. Results are
// composed from the on-disk fake-provider fixtures exactly as the backend bundle test composes them.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BriefDecoderProduct, briefDecoderDefinition } from "../src/products/briefDecoder/BriefDecoderProduct";
import {
  BRIEF_FIELDS,
  ISSUE_CATEGORIES,
  LEVELS,
  composeCopyText,
  extractBriefDecoderResult,
} from "../src/products/briefDecoder/parseBriefDecoder";
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
const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURE_ROOT = resolve(HERE, "../../../tests/fixtures/provider/fake_provider_outputs");
const SCHEMA_ROOT = resolve(
  HERE,
  "../../../packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/brief_decoder/schemas",
);

type EnumProp = { enum: string[] };
type OutputSchema = {
  properties: {
    brief: { properties: { values: { properties: Record<string, unknown> } } };
    issues: { items: { properties: { category: EnumProp; severity: EnumProp } } };
    questions: { items: { properties: { category: EnumProp; priority: EnumProp } } };
  };
};
type InputSchema = { properties: { brief_text: { maxLength: number } } };
function schema<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(SCHEMA_ROOT, name), "utf8")) as T;
}

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

  it("copies the schema's enums and brief_text length limit (drift guard)", () => {
    const output = schema<OutputSchema>("decode_output.schema.json");
    const issue = output.properties.issues.items.properties;
    const question = output.properties.questions.items.properties;
    expect([...BRIEF_FIELDS]).toEqual(Object.keys(output.properties.brief.properties.values.properties));
    expect([...ISSUE_CATEGORIES]).toEqual(issue.category.enum);
    expect([...LEVELS]).toEqual(issue.severity.enum);
    expect([...LEVELS]).toEqual(question.priority.enum);
    expect(question.category.enum).toEqual(issue.category.enum);

    const max = schema<InputSchema>("decode_input.schema.json").properties.brief_text.maxLength;
    const validate = (briefText: string) => briefDecoderDefinition.validate({ briefText }).briefText;
    expect(validate("a".repeat(max))).toBeUndefined();
    expect(validate("a".repeat(max + 1))).toEqual({ code: "max_length", maxLength: max });
    expect(validate("😀".repeat(max))).toBeUndefined();
  });

  it("requires a non-blank brief and trims outer whitespace the way the backend pattern does", () => {
    const validate = (briefText: string) => briefDecoderDefinition.validate({ briefText }).briefText;
    const toInput = (briefText: string) => briefDecoderDefinition.toInput({ briefText });
    for (const blank of ["", "   ", "\n", "\u0085", "\u001f \u3000"]) {
      expect(validate(blank)).toEqual({ code: "required" });
    }
    // A pasted trailing newline is trimmed, not rejected.
    expect(validate("brief\n")).toBeUndefined();
    expect(toInput("  brief text\n")).toEqual({ brief_text: "brief text" });
    // Python `\s` matches U+0085 and U+001C-U+001F (JS trim() does not) ...
    for (const edge of ["\u0085", "\u001c", "\u001f"]) {
      expect(toInput(`brief${edge}`)).toEqual({ brief_text: "brief" });
      expect(toInput(`${edge}brief`)).toEqual({ brief_text: "brief" });
    }
    // ... and does not match U+FEFF (JS trim() does), which the backend accepts as content.
    expect(toInput("\ufeffbrief\ufeff")).toEqual({ brief_text: "\ufeffbrief\ufeff" });
    // Inner whitespace is untouched.
    expect(toInput("a\n\nb")).toEqual({ brief_text: "a\n\nb" });
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
    expect(extractBriefDecoderResult({ ...good, issues: [{ category: "ambiguity", severity: "low", description: "d", evidence: 3 }] })).toBeNull();
    expect(extractBriefDecoderResult({ ...good, questions: [{ question: "q", rationale: "r", priority: "low" }] })).toBeNull();
    expect(extractBriefDecoderResult({ ...good, brief: { values: { budget: 5 } } })).toBeNull();
    // missing_fields is not rendered, so its absence must not discard an otherwise usable result.
    expect(extractBriefDecoderResult({ ...good, brief: { values: { project_goal: "g" } } })).not.toBeNull();
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
    expect(screen.getAllByRole("listitem").length).toBeGreaterThan(0);
    const list = document.querySelector("ol")!;
    expect(list.querySelectorAll(":scope > li")).toHaveLength(expected.questions.length);
    const LABEL = { low: "Low", medium: "Medium", high: "High" } as const;
    for (const issue of expected.issues) {
      expect(screen.getAllByText(issue.description).length).toBeGreaterThan(0);
      if (issue.evidence) {
        expect(screen.getAllByText(`Evidence: ${issue.evidence}`).length).toBeGreaterThan(0);
      }
      expect(screen.getAllByText(new RegExp(`· ${LABEL[issue.severity]} severity$`)).length).toBeGreaterThan(0);
    }
    for (const question of expected.questions) {
      expect(within(list).getByText(question.question)).toBeTruthy();
      expect(within(list).getByText(new RegExp(`^Why ask: ${question.rationale.slice(0, 30)}.* · .+ · ${LABEL[question.priority]} priority$`))).toBeTruthy();
    }
    const missing = BRIEF_FIELDS.filter((field) => expected.brief.values[field] === undefined);
    expect(screen.queryAllByText("Not provided")).toHaveLength(missing.length);
    expect(completedEvents(events)).toEqual([
      { type: "scenario_completed", scenarioSessionId: "session_1", guestId: "guest_1", resultViewed: true },
    ]);

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
    expect(completedEvents(events).map((event) => (event as { resultViewed: boolean }).resultViewed)).toEqual([true]);
  });

  it("renders both empty states for no issues, reports resultViewed false, and still copies", async () => {
    const events: ProductRunEvent[] = [];
    await decode(routes(composedOutput(".no_issues")), events);
    await waitFor(() => expect(screen.getByText("No issues found.")).toBeTruthy());
    expect(screen.getByText("No clarifying questions were generated.")).toBeTruthy();
    expect(completedEvents(events)).toEqual([
      { type: "scenario_completed", scenarioSessionId: "session_1", guestId: "guest_1", resultViewed: false },
    ]);
    // The empty question list must not read as a readiness claim; the rationale/priority chrome is absent.
    expect(document.querySelector("ol")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
  });

  it("the exported wrapper wires onEvent and visitId into the shared runtime", async () => {
    const events: ProductRunEvent[] = [];
    const { client } = makeClient(routes(composedOutput("")));
    render(<BriefDecoderProduct client={client} onEvent={(event) => events.push(event)} visitId="visit_1" />);
    await waitFor(() => expect(screen.getByLabelText("Client brief")).toBeTruthy());
    expect(events).toEqual([{ type: "product_viewed", guestId: "guest_1" }]);
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
