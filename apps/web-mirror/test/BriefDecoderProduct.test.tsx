// Brief Decoder's own meaning: the brief_text mapping, the four-part composite result, the
// contract's copy composition, and the activation rule (`web.result_viewed` only for a non-empty
// question list). Shared runtime behavior is proven once in ProductRunPage.test.tsx. Results are
// composed from the on-disk fake-provider fixtures exactly as the backend bundle test composes them.
import { createTranslator } from "use-intl";
import { BriefDecoderResultView } from "../src/products/briefDecoder/BriefDecoderResult";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { chooseAttachSession, useAttachSession, readAttachSessionId } from "../src/products/runtime/attachSession";
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
  composeQuestionsCopyText,
  extractBriefDecoderResult,
  hasQuestions,
  type ClarifyingQuestion,
} from "../src/products/briefDecoder/parseBriefDecoder";
import { BRIEF_DECODER_MESSAGES } from "../src/products/briefDecoder/messages";
import { ProductRunPage } from "../src/products/runtime/ProductRunPage";
import type { ProductRunEvent } from "../src/products/runtime/productDefinition";
import {
  errorResponse,
  guestIdentityResponse,
  idempotencyKeyOf,
  makeClient,
  makeClientWithDeferredCalls,
  quotaResponse,
  resultResponse,
  routesFor,
  runtimeConfigResponse,
  sessionResponse,
  startResponse,
} from "./fixtures/platformResponses";
import { makeRender } from "./support/renderWithI18n";
import { expectDataProcessingNotice } from "./support/expectDataProcessingNotice";
import { simulateBrowserTranslation } from "@anytoolai/shared-ui/test/support/simulateBrowserTranslation";
import { LOCALES, type Translate } from "../src/i18n";
import { LOCALE_STORAGE_KEY } from "../src/i18n/localeStorage";

const render = makeRender(BRIEF_DECODER_MESSAGES);
const enT = createTranslator({ locale: "en", messages: BRIEF_DECODER_MESSAGES.en }) as Translate;
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
// The backend now also returns the caller's original brief as `brief_text` (the handoff source,
// excluded from the rendered analysis and its copy text).
const RAW_BRIEF_SENTINEL = "RAW-BRIEF-SENTINEL-must-not-render";
const MISSING_TASK_HINT = "Describe what the client wants you to do or deliver. For example, “Write a recipe for our newsletter.”";
const reportedInputs = [
  "asdf ::: 12345 !!!",
  "Рецепт борща: свёкла, капуста, говядина. Варить два часа.",
] as const;

function composedOutput(suffix: "" | ".weak_input" | ".no_issues" | ".missing_task"): Record<string, unknown> {
  return {
    brief_text: RAW_BRIEF_SENTINEL,
    brief: fixture("extract_brief", suffix),
    issues: (fixture("detect_issues", suffix) as { issues: unknown[] }).issues,
    questions: suffix === ".no_issues" ? [] : (fixture("generate_questions", suffix) as { questions: unknown[] }).questions,
    document: fixture("generate_summary", suffix),
  };
}

afterEach(() => {
  vi.unstubAllEnvs();
  cleanup();
  window.localStorage.clear();
  window.sessionStorage.clear();
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
    [ROUTES.RESULT]: [resultResponse(IDS, {
      output,
      schema_ref: "brief_decoder.decode_output_v1",
      schema_version: 2,
    })],
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
  it.each(LOCALES)("example brief passes the validator in %s", (locale) => {
    expect(briefDecoderDefinition.validate(BRIEF_DECODER_MESSAGES[locale].decode.example.inputs)).toEqual({});
  });

  it("requires an authored question to count a saved result as viewed", () => {
    const result = extractBriefDecoderResult(composedOutput(""))!;
    const question = result.questions[0]!;
    expect(hasQuestions({ ...result, questions: [{ ...question, question: "\u200b" }] })).toBe(false);
    expect(hasQuestions({ ...result, questions: [{ ...question, question: "\u200b" }, question] })).toBe(true);
  });

  it("shows an example while keeping the typed brief", async () => {
    const { client } = makeClient(routes(composedOutput("")));
    render(<BriefDecoderProduct client={client} />);
    const field = await screen.findByLabelText<HTMLTextAreaElement>("Client brief");
    fireEvent.change(field, { target: { value: "My own bakery brief." } });
    const details = screen.getByTestId<HTMLDetailsElement>("first-run-example");
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(field.value).toBe("My own bakery brief.");
    expect(screen.getByText(BRIEF_DECODER_MESSAGES.en.decode.example.inputs.briefText)).toBeTruthy();
  });

  it("shows the shared processing notice and policy inside the form", async () => {
    vi.stubEnv("NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL", "https://example.com/privacy");
    const { client } = makeClient(routes(composedOutput("")));
    render(<BriefDecoderProduct client={client} />);
    const form = await screen.findByRole("form");
    expectDataProcessingNotice(form, "https://example.com/privacy");
  });

  it("does not promise draft recovery when unsent input is lost on remount", async () => {
    const { client } = makeClient(routes(composedOutput("")));
    const first = render(<BriefDecoderProduct client={client} />);
    const field = await screen.findByLabelText("Client brief");
    fireEvent.change(field, { target: { value: "An unsent client brief." } });
    expect(screen.getByText(/may be lost if you reload or leave the page/)).toBeTruthy();
    expect(screen.queryByText(/until you close it/)).toBeNull();
    first.unmount();

    const reloaded = makeClient(routes(composedOutput("")));
    render(<BriefDecoderProduct client={reloaded.client} />);
    expect((await screen.findByLabelText("Client brief") as HTMLTextAreaElement).value).toBe("");
    expect(screen.getByText(/may be lost if you reload or leave the page/)).toBeTruthy();
  });

  it.each([
    { locale: "en", translated: true },
    { locale: "ru", translated: false },
    { locale: "ru", translated: true },
  ] as const)("keeps decoding in $locale with translation=$translated (ANY-840)", async ({ locale, translated }) => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    const labels = locale === "ru"
      ? { brief: "Бриф клиента", submit: "Разобрать бриф", regenerate: "Разобрать бриф заново", result: "Разбор брифа", noIssues: "Проблем не найдено." }
      : { brief: "Client brief", submit: "Decode brief", regenerate: "Decode brief again", result: "Decoded brief", noIssues: "No issues found." };
    const errorSpy = vi.spyOn(console, "error");
    try {
      const { client, calls } = makeClient({
        ...routes(composedOutput("")),
        [ROUTES.QUOTA]: Array.from({ length: 5 }, () => quotaResponse(IDS)),
        [ROUTES.START]: [startResponse(), startResponse()],
        [ROUTES.SESSION]: [sessionResponse(), sessionResponse()],
        [ROUTES.RESULT]: [
          resultResponse(IDS, { output: composedOutput("") }),
          resultResponse(IDS, { output: composedOutput(".no_issues") }),
        ],
      });
      render(<BriefDecoderProduct client={client} />);
      fireEvent.change(await screen.findByLabelText(labels.brief), { target: { value: "Need a website by the holidays." } });
      const button = screen.getByRole("button", { name: labels.submit });
      if (translated) simulateBrowserTranslation(button);
      fireEvent.click(button);
      await screen.findByRole("button", { name: labels.regenerate });
      expect(screen.getByRole("heading", { name: labels.result, level: 2 })).toBeTruthy();

      if (translated) simulateBrowserTranslation(button);
      fireEvent.click(button);
      await screen.findByText(labels.noIssues);
      expect(screen.getByRole("button", { name: labels.regenerate })).toBe(button);
      expect(calls.filter((call) => call.key === ROUTES.START)).toHaveLength(2);
      expect(errorSpy).not.toHaveBeenCalled();
    } finally {
      errorSpy.mockRestore();
    }
  });

  it("declares the backend's Brief Decoder -> Acceptance Builder handoff and its button label", () => {
    const handoffs = readFileSync(
      resolve(SCHEMA_ROOT, "../handoffs.yaml"),
      "utf8",
    );
    const { handoffDefinitionId, targetProductId } = briefDecoderDefinition.handoff!;
    // The route's own block in handoffs.yaml names this id and this target product.
    const block = handoffs.split(/\n {2}- handoff_id: /).find((entry) => entry.startsWith(handoffDefinitionId));
    expect(block).toContain(`target_product_id: ${targetProductId}`);
    expect(BRIEF_DECODER_MESSAGES.en.decode.continueToTarget).toBeTruthy();
  });

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
    // brief.values is closed: an unknown key is rejected, not silently dropped.
    expect(extractBriefDecoderResult({ ...good, brief: { values: { project_goal: "x", invented: "y" } } })).toBeNull();
    // Legacy artifacts derive missing_fields from absent values.
    expect(extractBriefDecoderResult({ ...good, brief: { values: { project_goal: "g" } } })?.brief.missingFields)
      .toEqual(BRIEF_FIELDS.filter((field) => field !== "project_goal"));
    for (const missing_fields of [["nope"], ["deadline", 3], "deadline", null, {}]) {
      expect(extractBriefDecoderResult({ ...good, brief: { values: {}, missing_fields } })).toBeNull();
    }
    expect(extractBriefDecoderResult({})).toBeNull();
  });

  it.each(BRIEF_FIELDS)("rejects overlapping, omitted and duplicate missing metadata for %s", (field) => {
    const good = composedOutput("");
    const others = BRIEF_FIELDS.filter((candidate) => candidate !== field);
    const stated = field === "deliverables" || field === "constraints" ? ["stated"] : "stated";
    expect(extractBriefDecoderResult({ ...good, brief: { values: { [field]: stated }, missing_fields: [...BRIEF_FIELDS] } })).toBeNull();
    expect(extractBriefDecoderResult({ ...good, brief: { values: {}, missing_fields: others } })).toBeNull();
    expect(extractBriefDecoderResult({ ...good, brief: { values: {}, missing_fields: [...BRIEF_FIELDS, field] } })).toBeNull();
  });

  it("accepts every valid field partition, normalizes order and derives legacy missing metadata", () => {
    const good = composedOutput("");
    for (let mask = 0; mask < 2 ** BRIEF_FIELDS.length; mask++) {
      const present = BRIEF_FIELDS.filter((_, index) => mask & (1 << index));
      const values = Object.fromEntries(present.map((field) => [field, field === "deliverables" || field === "constraints" ? ["stated"] : "stated"]));
      const missing = BRIEF_FIELDS.filter((field) => !present.includes(field));
      for (const brief of [{ values }, { values, missing_fields: [...missing].reverse() }]) {
        expect(extractBriefDecoderResult({ ...good, brief })?.brief).toEqual({ values, missingFields: missing });
      }
    }
  });

  it("composes the copy text per renderer_contract.yaml", () => {
    const t = (key: string, values?: Record<string, string | number>) => values ? `${key}(${Object.values(values).join(",")})` : key;
    expect(composeCopyText({
      brief: { values: { project_goal: "G", deliverables: ["d1", "d2"] }, missingFields: ["deadline", "target_audience"] },
      issues: [
        { category: "ambiguity", severity: "high", description: "D1", evidence: "E1" },
        { category: "scope_risk", severity: "low", description: "D2" },
        { category: "budget_risk", severity: "medium", description: "D3", evidence: "" },
      ],
      questions: [
        { question: "Q1?", rationale: "not copied", priority: "high", category: "ambiguity" },
        { question: "Q2?", rationale: "not copied", priority: "low", category: "scope_risk" },
      ],
    }, t)).toBe([
      "result.brief\nbriefFields.project_goal: G\nbriefFields.deliverables:\n- d1\n- d2",
      "copy.missingFields\n- briefFields.deadline\n- briefFields.target_audience",
      "result.issues\n- categories.ambiguity · severity.high: D1\n  result.evidence(E1)\n- categories.scope_risk · severity.low: D2\n- categories.budget_risk · severity.medium: D3",
      "result.questions(2)\n1. Q1?\n2. Q2?",
    ].join("\n\n"));
  });

  it("omits an empty missing-field block and preserves the empty issue/question states", () => {
    const values = Object.fromEntries(BRIEF_FIELDS.map((field) => [field, "stated"]));
    expect(composeCopyText({ brief: { values, missingFields: [] }, issues: [], questions: [] }, enT)).toBe([
      "Brief\nProject goal: stated\nDeliverables: stated\nDeadline: stated\nBudget: stated\nTarget audience: stated\nConstraints: stated",
      "Issues\nNo issues found.",
      "0 clarifying questions\nNo clarifying questions were generated.",
    ].join("\n\n"));
  });

  it("lists all missing labels for an empty brief and keeps all five questions", () => {
    const output = composedOutput("");
    output.brief = { values: {} };
    const result = extractBriefDecoderResult(output)!;
    result.questions = Array.from({ length: 5 }, (_, index) => ({ ...result.questions[0]!, question: `Question ${index + 1}?` }));
    const copy = composeCopyText(result, enT);
    expect(copy).toContain("Brief\n\nNot stated in the brief\n- Project goal\n- Deliverables\n- Deadline\n- Budget\n- Target audience\n- Constraints");
    expect(copy).toContain("5 clarifying questions\n1. Question 1?\n2. Question 2?\n3. Question 3?\n4. Question 4?\n5. Question 5?");
  });

  it("copies whitespace, newlines, URLs, quotes and ICU argument braces verbatim", () => {
    const verbatim = '  Keep {rights} and "quotes"\nhttps://example.com/a?x={b}  ';
    const result = extractBriefDecoderResult(composedOutput(""))!;
    result.brief.values = { project_goal: verbatim, deliverables: [verbatim] };
    result.issues = [{ category: "ambiguity", severity: "low", description: verbatim, evidence: verbatim }];
    result.questions = [{ question: verbatim, rationale: "excluded", priority: "low", category: "ambiguity" }];
    const copy = composeCopyText(result, enT);
    expect(copy).toContain(`Project goal: ${verbatim}\nDeliverables:\n- ${verbatim}`);
    expect(copy).toContain(`- Ambiguity · Low severity: ${verbatim}\n  Evidence: ${verbatim}`);
    expect(copy).toContain(`1. ${verbatim}`);
    expect(copy).not.toContain("excluded");
  });

  it("copies only authored question text in input order, without adding numbering or a trailing line", () => {
    const question: ClarifyingQuestion = { question: "What is the budget?", rationale: "excluded", priority: "low", category: "ambiguity" };
    const other = { ...question, question: "Who signs off?", priority: "high" } as const;
    expect(composeQuestionsCopyText([])).toBe("");
    expect(composeQuestionsCopyText([question])).toBe("What is the budget?");
    expect(composeQuestionsCopyText([question, other, question])).toBe("What is the budget?\nWho signs off?\nWhat is the budget?");
    const invisible = { ...question, question: " \u200b\u00ad\r\n\u2060 " };
    expect(composeQuestionsCopyText([invisible])).toBe("");
    expect(composeQuestionsCopyText([invisible, question, invisible])).toBe("What is the budget?");
    expect(composeQuestionsCopyText([
      { ...question, question: '  ¿Cuál es el {presupuesto}? \r\n\t¿En euros?\n\n  ¿Con IVA?  ' },
      { ...other, question: " Кто\v\f\u0085\u2028\u2029 утверждает?" },
    ])).toBe("¿Cuál es el {presupuesto}? ¿En euros? ¿Con IVA?\nКто утверждает?");
  });

  it("does not offer question copy for historical invisible-only entries", () => {
    const result = extractBriefDecoderResult(composedOutput(""))!;
    result.questions = [{ ...result.questions[0]!, question: "\u200b" }];
    render(<BriefDecoderResultView result={result} onCopy={vi.fn().mockResolvedValue(true)} />);
    expect(screen.queryByRole("button", { name: "Copy questions" })).toBeNull();
    expect(screen.getByRole("button", { name: "Copy" })).toBeTruthy();
  });

  it.each([false, true])("keeps the questions fallback local and allows retry (rejection=%s)", async (rejection) => {
    const result = extractBriefDecoderResult(composedOutput(".weak_input"))!;
    const expected = result.questions.map(({ question }) => question).join("\n");
    const onCopy = vi.fn<(text: string) => Promise<boolean>>().mockResolvedValue(true);
    if (rejection) onCopy.mockRejectedValueOnce(new Error("Clipboard blocked"));
    else onCopy.mockResolvedValueOnce(false);
    render(<BriefDecoderResultView result={result} onCopy={onCopy} />);
    const section = within(screen.getByRole("region", { name: "4 clarifying questions" }));
    fireEvent.click(section.getByRole("button", { name: "Copy questions" }));
    expect((await section.findByRole("alert")).textContent).toMatch(/could not copy to clipboard/i);
    const select = section.getByRole("button", { name: "Select text" });
    expect(screen.getAllByRole("button", { name: "Select text" })).toHaveLength(1);
    fireEvent.click(select);
    expect(window.getSelection()?.toString()).toBe(expected);
    expect(screen.getByRole("button", { name: "Copy" })).toBeTruthy();
    fireEvent.click(section.getByRole("button", { name: "Copy questions" }));
    expect(await section.findByRole("button", { name: "Questions copied" })).toBeTruthy();
    expect(section.queryByRole("alert")).toBeNull();
    expect(onCopy.mock.calls).toEqual([[expected], [expected]]);
  });

  it.each(["", ".weak_input"] as const)("copy contains every value and every question verbatim, and nothing from document (%s)", async (suffix) => {
    const output = composedOutput(suffix);
    const sentinel = "LLM_DOCUMENT_ONLY_SENTINEL";
    const original = extractBriefDecoderResult(output)!;
    output.document = { summary: sentinel, sections: original.document.sections.map(() => ({ title: sentinel, content: sentinel })) };
    const result = extractBriefDecoderResult(output)!;
    const onCopy = vi.fn<(text: string) => Promise<boolean>>().mockResolvedValue(true);
    render(<BriefDecoderResultView result={result} onCopy={onCopy} />);
    expect(within(screen.getByRole("region", { name: "Summary document" })).getAllByText(sentinel).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await screen.findByRole("button", { name: "Copied" });
    expect(onCopy).toHaveBeenCalledTimes(1);
    const copy = onCopy.mock.calls[0]![0];
    for (const value of Object.values(result.brief.values)) {
      for (const item of Array.isArray(value) ? value : [value]) expect(copy).toContain(item);
    }
    for (const question of result.questions) expect(copy).toContain(question.question);
    expect(copy.match(/^\d+\. /gm)).toHaveLength(result.questions.length);
    for (const issue of result.issues) expect(copy).toContain(issue.description);
    expect(copy).not.toContain(sentinel);
    expect(copy).not.toContain(RAW_BRIEF_SENTINEL);
    expect(copy).not.toMatch(/\b(project_goal|target_audience)\b/);
    if (suffix === ".weak_input") {
      expect(copy).toContain("Not stated in the brief");
      for (const field of result.brief.missingFields) expect(copy).toContain(`- ${BRIEF_DECODER_MESSAGES.en.briefFields[field]}`);
    }
  });

  it("reveals the structured text for manual selection when the clipboard is blocked", async () => {
    const result = extractBriefDecoderResult(composedOutput(""))!;
    const onCopy = vi.fn<(text: string) => Promise<boolean>>().mockResolvedValue(false);
    render(<BriefDecoderResultView result={result} onCopy={onCopy} />);
    const copyButton = screen.getByRole("button", { name: "Copy" });
    expect(copyButton.parentElement!.parentElement!.querySelector("[hidden]")!.nextElementSibling).toBe(copyButton.parentElement);
    fireEvent.click(copyButton);
    const select = await screen.findByRole("button", { name: "Select text" });
    const copyText = select.parentElement!.previousElementSibling!;
    expect(copyText.textContent).toBe(composeCopyText(result, enT));
    fireEvent.click(select);
    expect(window.getSelection()?.toString()).toBe(composeCopyText(result, enT));
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

  it.each([
    ["", "Client brief: required."],
    [" \t\n ", "Client brief: required."],
    ["a".repeat(8001), "Client brief: 8,000 characters maximum."],
  ])("makes no start call for invalid input %#", async (briefText, message) => {
    const { client, calls } = makeClient(routes(composedOutput("")));
    render(<ProductRunPage definition={briefDecoderDefinition} client={client} />);
    const field = await screen.findByLabelText("Client brief");
    fireEvent.change(field, { target: { value: briefText } });
    fireEvent.click(screen.getByRole("button", { name: "Decode brief" }));
    expect(await screen.findByText(message)).toBeTruthy();
    expect(calls.some((call) => call.key === ROUTES.START)).toBe(false);
  });

  it.each(reportedInputs)("shows accessible feedback instead of an analysis for %s", async (briefText) => {
    const output = composedOutput(".missing_task");
    output.brief_text = briefText;
    if (briefText === reportedInputs[1]) {
      const goal = "Cook borscht for two hours";
      output.brief = { values: { project_goal: goal }, missing_fields: BRIEF_FIELDS.filter((field) => field !== "project_goal") };
      output.issues = [
        { category: "missing_information", severity: "high", description: "The number of servings is unclear." },
        ...(output.issues as unknown[]),
      ];
      output.questions = [{
        category: "missing_information", priority: "high", source_issue_index: 0,
        question: "How many servings?", rationale: "The answer determines the quantities.",
      }];
    }
    const queues = routes(output);
    const nextSession = "GET /v1/scenario-sessions/session_2";
    const events: ProductRunEvent[] = [];
    const { client, calls } = makeClient({
      ...queues,
      [ROUTES.START]: [...queues[ROUTES.START], startResponse({ scenario_session_id: "session_2" })],
      [nextSession]: [sessionResponse({ scenario_session_id: "session_2" })],
      [ROUTES.RESULT]: [...queues[ROUTES.RESULT], resultResponse(IDS, { output: composedOutput(".weak_input") })],
    });
    render(<BriefDecoderProduct client={client} onEvent={(event) => events.push(event)} />);
    const field = await screen.findByLabelText<HTMLTextAreaElement>("Client brief");
    const rawDraft = `  ${briefText}\n`;
    fireEvent.change(field, { target: { value: rawDraft } });
    fireEvent.click(screen.getByRole("button", { name: "Decode brief" }));

    const hint = await screen.findByText(MISSING_TASK_HINT);
    expect(field.value).toBe(rawDraft);
    expect(field.getAttribute("aria-invalid")).toBe("true");
    expect(field.getAttribute("aria-describedby")?.split(" ")).toContain(hint.id);
    await waitFor(() => expect(document.activeElement).toBe(field));
    expect(screen.queryByRole("heading", { name: "Brief", level: 3 })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Summary document" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy questions" })).toBeNull();
    const handoffName = BRIEF_DECODER_MESSAGES.en.decode.continueToTarget;
    expect(screen.queryByRole("button", { name: handoffName })).toBeNull();
    expect(completedEvents(events)).toEqual([]);

    const submit = () => fireEvent.click(screen.getByRole("button", { name: "Decode brief" }));
    const starts = () => calls.filter((call) => call.key === ROUTES.START);
    submit();
    fireEvent.change(field, { target: { value: `\u0085${briefText}\n\t` } });
    submit();
    expect(screen.getByText(MISSING_TASK_HINT)).toBeTruthy();
    expect(starts()).toHaveLength(1);

    const correction = "Write a borscht recipe.";
    fireEvent.change(field, { target: { value: correction } });
    expect(screen.queryByText(MISSING_TASK_HINT)).toBeNull();
    expect(field.getAttribute("aria-invalid")).toBe("false");
    submit();
    expect(await screen.findByRole("button", { name: "Copy" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Copy questions" })).toBeTruthy();
    expect(screen.getByRole("button", { name: handoffName })).toBeTruthy();
    expect(starts()).toHaveLength(2);
    expect(JSON.parse(starts()[1]!.init.body as string)).toMatchObject({ input: { brief_text: correction } });
    expect(completedEvents(events)).toEqual([
      { type: "scenario_completed", scenarioSessionId: "session_2", guestId: "guest_1", resultViewed: true },
    ]);
  });

  it("clears an earlier good result when the next submission has no task", async () => {
    const queues = routes(composedOutput(""));
    const { client } = makeClient({
      ...queues,
      [ROUTES.START]: [...queues[ROUTES.START], startResponse({ scenario_session_id: "session_2" })],
      "GET /v1/scenario-sessions/session_2": [sessionResponse({ scenario_session_id: "session_2" })],
      [ROUTES.RESULT]: [...queues[ROUTES.RESULT], resultResponse(IDS, {
        scenario_session_id: "session_2",
        output: { ...composedOutput(".missing_task"), brief_text: reportedInputs[0] },
      })],
    });
    render(<BriefDecoderProduct client={client} />);
    const field = await screen.findByLabelText("Client brief");
    fireEvent.change(field, { target: { value: "A logo for our bakery." } });
    fireEvent.click(screen.getByRole("button", { name: "Decode brief" }));
    expect(await screen.findByRole("button", { name: "Copy" })).toBeTruthy();

    fireEvent.change(field, { target: { value: reportedInputs[0] } });
    fireEvent.click(screen.getByRole("button", { name: "Decode brief again" }));
    expect(await screen.findByText(MISSING_TASK_HINT)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy questions" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Summary document" })).toBeNull();
  });

  it("renders the four parts for the happy fixtures, emits one result_viewed, and copies the structured result", async () => {
    const output = composedOutput("");
    const expected = extractBriefDecoderResult(output)!;
    const events: ProductRunEvent[] = [];
    const { calls } = await decode(routes(output), events);

    await waitFor(() => expect(screen.getByRole("heading", { name: /clarifying questions/ })).toBeTruthy());
    // The workspace cards own the h2s; the four contract parts sit under the result card as h3s.
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(["Your details", "Decoded brief"]);
    expect(within(screen.getByRole("region", { name: "Decoded brief" })).getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
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
    // `scenario_completed` comes from a commit-time effect, so it can land just after the DOM does.
    await waitFor(() =>
      expect(completedEvents(events)).toEqual([
        { type: "scenario_completed", scenarioSessionId: "session_1", guestId: "guest_1", resultViewed: true },
      ]),
    );

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(composeCopyText(expected, enT));
    expect(document.body.textContent).not.toContain(RAW_BRIEF_SENTINEL);
    expect(JSON.stringify(vi.mocked(navigator.clipboard.writeText).mock.calls)).not.toContain(RAW_BRIEF_SENTINEL);
    const nextAction = calls.filter((call) => call.key === ROUTES.NEXT_ACTION);
    expect(nextAction).toHaveLength(1);
    expect(JSON.parse(nextAction[0].init.body as string)).toEqual({ checkpoint_id: "checkpoint_1" });
  });

  it("keeps the brief beside the result through edit, repeat, copy and a new task, reporting each result once", async () => {
    const events: ProductRunEvent[] = [];
    const routed = makeClientWithDeferredCalls(
      {
        [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
        [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
        [ROUTES.QUOTA]: [quotaResponse(IDS)],
        // Two distinct sessions: completion events are deduped per scenario session id.
        [ROUTES.START]: [startResponse(), startResponse({ scenario_session_id: "session_2" })],
        [ROUTES.SESSION]: [sessionResponse()],
        "GET /v1/scenario-sessions/session_2": [sessionResponse({ scenario_session_id: "session_2" })],
        [ROUTES.NEXT_ACTION]: [sessionResponse({ status: "completed" })],
        "POST /v1/scenario-sessions/session_2/next-actions/copy_result": [sessionResponse({ scenario_session_id: "session_2", status: "completed" })],
      },
      { [ROUTES.RESULT]: 2 },
    );
    render(<ProductRunPage definition={briefDecoderDefinition} client={routed.client} onEvent={(e) => events.push(e)} />);
    const brief = (await screen.findByLabelText("Client brief")) as HTMLTextAreaElement;
    fireEvent.change(brief, { target: { value: "Need a website by the holidays." } });
    fireEvent.click(screen.getByRole("button", { name: "Decode brief" }));
    await waitFor(() => expect(routed.calls.filter((call) => call.key === ROUTES.RESULT)).toHaveLength(1));
    routed.resolveCall(ROUTES.RESULT, 0, resultResponse(IDS, { output: composedOutput("") }));

    // Generation: the four parts sit in the result card, the brief stays in its own card.
    await screen.findByRole("heading", { name: /clarifying questions/, level: 3 });
    const resultCard = screen.getByRole("heading", { name: "Decoded brief", level: 2 }).closest("section")!;
    expect(within(resultCard).getByRole("button", { name: "Copy questions" })).toBeTruthy();
    expect(within(resultCard).getAllByRole("heading", { level: 3 })).toHaveLength(4);
    expect(brief.value).toBe("Need a website by the holidays.");
    expect(document.querySelectorAll("section[aria-labelledby] section[aria-labelledby]").length).toBe(4);

    // Edit: the decoded brief stays and is marked as made from earlier details.
    fireEvent.change(brief, { target: { value: "Need a website and a logo by the holidays." } });
    expect(within(resultCard).getByText("Created from previous details")).toBeTruthy();
    expect(within(resultCard).getByRole("heading", { name: /clarifying questions/ })).toBeTruthy();

    // Repeat: the previous result stays until the new one arrives; a fresh key is used.
    fireEvent.click(screen.getByRole("button", { name: "Decode brief again" }));
    await waitFor(() => expect(routed.calls.filter((call) => call.key === ROUTES.RESULT)).toHaveLength(2));
    const starts = routed.calls.filter((call) => call.key === ROUTES.START);
    expect(idempotencyKeyOf(starts[0]!)).not.toBe(idempotencyKeyOf(starts[1]!));
    expect(within(resultCard).getByRole("heading", { name: /clarifying questions/ })).toBeTruthy();
    expect(within(resultCard).getByText("Decoding your brief…")).toBeTruthy();
    expect(completedEvents(events)).toHaveLength(1);
    routed.resolveCall(ROUTES.RESULT, 1, resultResponse(IDS, { output: composedOutput(".no_issues") }));
    await screen.findByText("No issues found.");
    expect(screen.getByText("No clarifying questions were generated.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Copy questions" })).toBeNull();
    expect(screen.queryByText("Created from previous details")).toBeNull();
    // One completion per session; the zero-question rerun does not count as a viewed result.
    await waitFor(() => expect(completedEvents(events).map((e) => (e as { resultViewed: boolean }).resultViewed)).toEqual([true, false]));

    // Copy copies the structured result, in one group with "New task".
    const expected = extractBriefDecoderResult(composedOutput(".no_issues"))!;
    const copy = screen.getByRole("button", { name: "Copy" });
    const newTask = screen.getByRole("button", { name: "New task" });
    expect(copy.parentElement).toBe(newTask.parentElement);
    fireEvent.click(copy);
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(composeCopyText(expected, enT));

    // New task: brief and result cleared, focus back on the brief field.
    fireEvent.click(newTask);
    expect(brief.value).toBe("");
    expect(screen.queryByText("No issues found.")).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(brief));
    expect(completedEvents(events)).toHaveLength(2);
  });

  it("renders the weak-input fixtures, and copies only the four questions with one activation", async () => {
    const events: ProductRunEvent[] = [];
    const { calls } = await decode(routes(composedOutput(".weak_input")), events);
    await waitFor(() => expect(screen.getByRole("heading", { name: /clarifying questions/ })).toBeTruthy());
    expect(screen.getByRole("heading", { name: "4 clarifying questions" })).toBeTruthy();
    expect(screen.queryByText("No clarifying questions were generated.")).toBeNull();
    await waitFor(() =>
      expect(completedEvents(events).map((event) => (event as { resultViewed: boolean }).resultViewed)).toEqual([true]),
    );
    const section = within(screen.getByRole("region", { name: "4 clarifying questions" }));
    fireEvent.click(section.getByRole("button", { name: "Copy questions" }));
    expect(await section.findByRole("button", { name: "Questions copied" })).toBeTruthy();
    expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith([
      "What should the website do, and which pages or features do you need?",
      "When do you need the website to be ready?",
      "What budget do you have in mind for this project?",
      'What does "nice" mean to you -- can you share an example of a website you like?',
    ].join("\n"));
    expect(screen.getByRole("button", { name: "Copy" })).toBeTruthy();
    const nextAction = calls.filter((call) => call.key === ROUTES.NEXT_ACTION);
    expect(nextAction).toHaveLength(1);
    expect(JSON.parse(nextAction[0]!.init.body as string)).toEqual({ checkpoint_id: "checkpoint_1" });
    expect(completedEvents(events)).toHaveLength(1);
  });

  it("renders both empty states for no issues, reports resultViewed false, and still copies", async () => {
    const events: ProductRunEvent[] = [];
    await decode(routes(composedOutput(".no_issues")), events);
    await waitFor(() => expect(screen.getByText("No issues found.")).toBeTruthy());
    expect(screen.getByText("No clarifying questions were generated.")).toBeTruthy();
    await waitFor(() =>
      expect(completedEvents(events)).toEqual([
        { type: "scenario_completed", scenarioSessionId: "session_1", guestId: "guest_1", resultViewed: false },
      ]),
    );
    // The empty question list must not read as a readiness claim; the rationale/priority chrome is absent.
    expect(document.querySelector("ol")).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy questions" })).toBeNull();

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

function AttachedBriefDecoderProduct({ client, sessionId }: { client: PlatformApiClient; sessionId?: string }) {
  const attach = useAttachSession("brief_decoder", sessionId);
  return <BriefDecoderProduct client={client} {...attach} />;
}

function versionTwoRuntimeConfig() {
  return runtimeConfigResponse(IDS, {
    scenarios: [{
      scenario_id: IDS.scenarioId,
      version: 1,
      allowed_next_actions: ["copy_result"],
      input_renderer_hint: { renderer: "json_schema", schema_ref: "brief_decoder.decode_input_v1", schema_version: 1 },
      output_renderer_hint: { renderer: "json_schema", schema_ref: "brief_decoder.decode_output_v1", schema_version: 2 },
    }],
  });
}

it.each([
  { fromLink: true, briefText: reportedInputs[0] },
  { fromLink: false, briefText: reportedInputs[1] },
])("restores rejected input from a result link or tab recovery (link=$fromLink)", async ({ fromLink, briefText }) => {
  if (!fromLink) expect(chooseAttachSession("brief_decoder", "session_1", "")).toBe(true);
  const rejected = routes({ ...composedOutput(".missing_task"), brief_text: briefText });
  const { client, calls } = makeClient({
    ...rejected,
    [ROUTES.RUNTIME_CONFIG]: [versionTwoRuntimeConfig()],
    [ROUTES.START]: [startResponse({ scenario_session_id: "session_2" })],
    [ROUTES.SESSION]: Array.from({ length: 3 }, () => sessionResponse({ scenario_id: IDS.scenarioId })),
    "GET /v1/scenario-sessions/session_2": [sessionResponse({ scenario_session_id: "session_2" })],
    [ROUTES.RESULT]: [
      ...rejected[ROUTES.RESULT],
      resultResponse(IDS, { scenario_session_id: "session_2", output: composedOutput(".weak_input") }),
    ],
  });
  render(<AttachedBriefDecoderProduct client={client} sessionId={fromLink ? "session_1" : undefined} />);

  const hint = await screen.findByText(MISSING_TASK_HINT);
  const field = screen.getByLabelText<HTMLTextAreaElement>("Client brief");
  expect(field.value).toBe(briefText);
  expect(field.getAttribute("aria-describedby")?.split(" ")).toContain(hint.id);
  await waitFor(() => expect(document.activeElement).toBe(field));
  expect(readAttachSessionId("brief_decoder")).toBeUndefined();
  expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Copy questions" })).toBeNull();
  const submit = () => fireEvent.click(screen.getByRole("button", { name: "Decode brief" }));
  const starts = () => calls.filter((call) => call.key === ROUTES.START);
  submit();
  fireEvent.change(field, { target: { value: ` ${briefText}\n` } });
  submit();
  expect(screen.getByText(MISSING_TASK_HINT)).toBeTruthy();
  expect(starts()).toHaveLength(0);

  const corrected = "Write a borscht recipe.";
  fireEvent.change(field, { target: { value: corrected } });
  expect(screen.queryByText(MISSING_TASK_HINT)).toBeNull();
  submit();
  expect(await screen.findByRole("button", { name: "Copy" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Copy questions" })).toBeTruthy();
  expect(starts()).toHaveLength(1);
  expect(JSON.parse(starts()[0]!.init.body as string)).toMatchObject({ input: { brief_text: corrected } });
});

it.each(LOCALES)("renders a legacy question category as a localized label in %s", (locale) => {
  window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  const result = extractBriefDecoderResult({
    ...composedOutput(".weak_input"),
    questions: fixture("generate_questions", ".legacy_question_category").questions,
  })!;
  render(<BriefDecoderResultView result={result} onCopy={vi.fn()} />);
  const label = BRIEF_DECODER_MESSAGES[locale].categories.missing_task_description;
  const question = screen.getByText(result.questions[0]!.question, { selector: "li > div" });
  expect(question.parentElement?.textContent).toContain(label);
  expect(question.parentElement?.textContent).not.toContain("categories.missing_task_description");
});

it.each([false, true])("restores a version 2 result with ordinary gaps after reload (poll recovery=%s)", async (recover) => {
  const historicalResult = () => resultResponse(IDS, {
    output: {
      ...composedOutput(".weak_input"),
      questions: fixture("generate_questions", ".legacy_question_category").questions,
    },
    schema_ref: "brief_decoder.decode_output_v1",
    schema_version: 2,
  });
  const queues = {
    ...routes(composedOutput(".weak_input")),
    [ROUTES.RESULT]: [historicalResult(), historicalResult()],
  };
  const { client, calls } = makeClient({
    ...queues,
    [ROUTES.RUNTIME_CONFIG]: [versionTwoRuntimeConfig(), versionTwoRuntimeConfig()],
    [ROUTES.QUOTA]: Array.from({ length: 4 }, () => quotaResponse(IDS, { used_count: 1, remaining_count: 2 })),
    [ROUTES.SESSION]: [
      ...(recover ? [errorResponse(503, "internal_error")] : []),
      sessionResponse({ scenario_id: IDS.scenarioId }), sessionResponse({ scenario_id: IDS.scenarioId }), sessionResponse({ scenario_id: IDS.scenarioId }),
    ],
  });
  const first = render(<AttachedBriefDecoderProduct client={client} sessionId="session_1" />);
  if (recover) {
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
  }
  await screen.findByRole("button", { name: "New task" });
  expect(readAttachSessionId("brief_decoder")).toBe("session_1");
  first.unmount();
  render(<AttachedBriefDecoderProduct client={client} />);
  await screen.findByRole("button", { name: "New task" });
  expect(screen.getByRole("heading", { name: "4 clarifying questions" })).toBeTruthy();
  expect(screen.queryByText(MISSING_TASK_HINT)).toBeNull();
  expect(calls.filter((call) => call.key === ROUTES.SESSION)).toHaveLength(recover ? 4 : 3);
  expect(calls.some((call) => call.key.endsWith("/start"))).toBe(false);
  expect(screen.getByText(/2 of 3/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "New task" }));
  expect(readAttachSessionId("brief_decoder")).toBeUndefined();
});
