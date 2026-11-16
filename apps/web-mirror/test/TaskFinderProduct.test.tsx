import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TaskFinderProduct, taskFinderDefinition as definition } from "../src/products/taskFinder/TaskFinderProduct";
import { TaskFinderResultView } from "../src/products/taskFinder/TaskFinderResult";
import { TASK_FINDER_MESSAGES } from "../src/products/taskFinder/messages";
import { CRITERIA, VERDICTS, STATUSES, parseTaskFinder, composeCopyText } from "../src/products/taskFinder/parseTaskFinder";
import { LOCALE_STORAGE_KEY } from "../src/i18n/localeStorage";
import type { ProductRunEvent } from "../src/products/runtime/productDefinition";
import { makeRender } from "./support/renderWithI18n";
import { makeClientCapturingRequests, routesFor, guestIdentityResponse, runtimeConfigResponse, quotaResponse, startResponse, sessionResponse, resultResponse, errorResponse } from "./fixtures/platformResponses";

const render = makeRender(TASK_FINDER_MESSAGES);
const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURES = resolve(HERE, "../../../tests/fixtures/provider/fake_provider_outputs");
const PRODUCT = resolve(HERE, "../../../packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/task_finder");
type Comparison = { verdict: string; confidence: number; deltas: { criterion_id: string; status: string; evidence: string }[]; rationale: string };
type Match = { criterion_scores: { criterion_id: string; score: number; rationale: string }[]; score: number; strengths: string[]; gaps: string[]; overall_rationale: string };
function fixture<T>(action: string, suffix: string): T {
  return (JSON.parse(readFileSync(resolve(FIXTURES, `task_finder.${action}_v1${suffix}.json`), "utf8")) as { response_json: T }).response_json;
}
function output(suffix = "") {
  return { task_text: "TASK_ECHO_SENTINEL", freelancer_positioning: "PROFILE_ECHO_SENTINEL",
    comparison: fixture<Comparison>("compare", suffix), match: fixture<Match>("score", suffix) };
}
function expectedCopy(raw: ReturnType<typeof output>): string {
  const labels = ["Skills fit", "Experience fit", "Scope fit", "Constraints fit"];
  return [
    `Fit\nFit score: ${raw.match.score}/100. ${raw.match.overall_rationale}\nVerdict: ${raw.comparison.verdict.replace("_", " ")}. ${raw.comparison.rationale}`,
    `Criteria\n${raw.comparison.deltas.map((d, i) => `${labels[i]}: ${d.status}. ${d.evidence}`).join("\n")}`,
    `Criterion scores\n${raw.match.criterion_scores.map((s, i) => `${labels[i]}: ${s.score}/100. ${s.rationale}`).join("\n")}`,
    `Strengths\n${raw.match.strengths.length ? raw.match.strengths.map((s) => `- ${s}`).join("\n") : "Not specified."}`,
    `Gaps\n${raw.match.gaps.length ? raw.match.gaps.map((s) => `- ${s}`).join("\n") : "Not specified."}`,
  ].join("\n\n");
}
const ids = { productId: "task_finder", scenarioId: "task_finder.fit_v1" };
const r = routesFor(ids);
function routes(raw = output()) {
  return {
    [r.RUNTIME_CONFIG]: [runtimeConfigResponse(ids)], [r.GUEST_IDENTITY]: [guestIdentityResponse()],
    [r.QUOTA]: [quotaResponse(ids), quotaResponse(ids), quotaResponse(ids)],
    [r.START]: [startResponse()], [r.SESSION]: [sessionResponse()], [r.RESULT]: [resultResponse(ids, { output: raw })],
    [r.NEXT_ACTION]: [sessionResponse()],
  };
}
async function submit() {
  await waitFor(() => expect((screen.getByRole("button", { name: "Check fit" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText("Task description"), { target: { value: "Build a dashboard." } });
  fireEvent.change(screen.getByLabelText("Your profile"), { target: { value: "React developer." } });
  fireEvent.click(screen.getByRole("button", { name: "Check fit" }));
}
afterEach(() => { cleanup(); window.localStorage.clear(); window.sessionStorage.clear(); });
beforeEach(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: vi.fn(() => Promise.resolve()) } }));

describe("Task Finder input and contract", () => {
  it("pins scenario, enums, criterion ids and input limits to the backend schemas", () => {
    type Enum = { enum: string[] };
    const schema = JSON.parse(readFileSync(resolve(PRODUCT, "schemas/fit_output.schema.json"), "utf8")) as {
      properties: { comparison: { properties: { verdict: Enum } } };
      $defs: { delta: { properties: { criterion_id: Enum; status: Enum } }; criterion_score: { properties: { criterion_id: Enum } } };
    };
    expect(definition.scenarioId).toBe(ids.scenarioId);
    expect(Object.keys(VERDICTS)).toEqual(schema.properties.comparison.properties.verdict.enum);
    expect(Object.keys(CRITERIA)).toEqual(schema.$defs.delta.properties.criterion_id.enum);
    expect(Object.keys(CRITERIA)).toEqual(schema.$defs.criterion_score.properties.criterion_id.enum);
    expect(Object.keys(STATUSES)).toEqual(schema.$defs.delta.properties.status.enum);
    const input = JSON.parse(readFileSync(resolve(PRODUCT, "schemas/fit_input.schema.json"), "utf8")) as { properties: Record<string, { maxLength: number }> };
    for (const [field, backendField] of [["taskText", "task_text"], ["positioning", "freelancer_positioning"]] as const) {
      const max = input.properties[backendField].maxLength;
      expect(definition.validate({ taskText: "a", positioning: "b", [field]: "😀".repeat(max) })).toEqual({});
      expect(definition.validate({ taskText: "a", positioning: "b", [field]: "😀".repeat(max + 1) })[field]).toEqual({ code: "max_length", maxLength: max });
    }
    expect(definition.toInput({ taskText: "\n task \n", positioning: "\u0085 profile\t" })).toEqual({ task_text: "task", freelancer_positioning: "profile" });
  });
  it("pins copy blocks and exclusions to the renderer contract", () => {
    const contract = readFileSync(resolve(PRODUCT, "renderer_contract.yaml"), "utf8");
    expect([...contract.matchAll(/^ {8}title: (.+)$/gm)].map((m) => m[1])).toEqual(["Fit", "Criteria", "Criterion scores", "Strengths", "Gaps"]);
    expect(contract).toContain("excluded_fields: [task_text, freelancer_positioning, comparison.confidence]");
    expect(contract).toContain("next_action: copy_result");
    expect(composeCopyText(parseTaskFinder(output())!)).toBe(expectedCopy(output()));
  });
});

describe("Task Finder parser", () => {
  it.each(["", ".weak_input"])("accepts fixture %s without reconciling independent indicators", (suffix) => {
    const result = parseTaskFinder(output(suffix))!;
    expect(result.score).toBe(suffix ? 31 : 64);
    expect(result.verdict).toBe(suffix ? "partial_fit" : "weak_fit");
    expect(JSON.stringify(result)).not.toMatch(/SENTINEL|"confidence":/);
  });
  it("sorts both lists by criterion id", () => {
    const raw = output(); raw.comparison.deltas.reverse(); raw.match.criterion_scores.reverse();
    expect(parseTaskFinder(raw)).toEqual(parseTaskFinder(output()));
  });
  it.each(["missing", "duplicate", "unknown", "inherited"])("rejects %s criterion in either list", (kind) => {
    for (const field of ["deltas", "criterion_scores"] as const) {
      const raw = output(); const list = field === "deltas" ? raw.comparison.deltas : raw.match.criterion_scores;
      if (kind === "missing") list.pop();
      else list[0].criterion_id = kind === "duplicate" ? list[1].criterion_id : kind === "inherited" ? "toString" : "new_criterion";
      expect(parseTaskFinder(raw)).toBeNull();
    }
  });
  it.each([NaN, Infinity, -1, 101, "64", null])("rejects invalid score %s in either location", (value) => {
    const raw = output();
    expect(parseTaskFinder({ ...raw, match: { ...raw.match, score: value } })).toBeNull();
    expect(parseTaskFinder({ ...raw, match: { ...raw.match, criterion_scores: [{ ...raw.match.criterion_scores[0], score: value }, ...raw.match.criterion_scores.slice(1)] } })).toBeNull();
  });
  it.each(["unknown", "toString", "__proto__"])("rejects unknown verdict/status %s", (value) => {
    const raw = output(); raw.comparison.verdict = value; expect(parseTaskFinder(raw)).toBeNull();
    const other = output(); other.comparison.deltas[0].status = value; expect(parseTaskFinder(other)).toBeNull();
  });
  it("accepts fractional scores and empty lists", () => {
    const raw = output(); raw.match.score = 64.5; raw.match.strengths = []; raw.match.gaps = [];
    expect(composeCopyText(parseTaskFinder(raw)!)).toContain("Fit score: 64.5/100.");
    expect(composeCopyText(parseTaskFinder(raw)!)).toContain("Gaps\nNot specified.");
  });
});

describe("Task Finder page", () => {
  it("renders separate score/verdict, copies the exact contract text, activates once and resets", async () => {
    const made = makeClientCapturingRequests(routes()); const events: ProductRunEvent[] = [];
    render(<TaskFinderProduct client={made.client} onEvent={(e) => events.push(e)} />);
    await waitFor(() => expect(screen.getByText(TASK_FINDER_MESSAGES.en.description)).toBeTruthy());
    await waitFor(() => expect(screen.getByText("3 of 3 runs remaining.")).toBeTruthy());
    await submit();
    await waitFor(() => expect(screen.getByText("64 / 100")).toBeTruthy());
    expect(screen.getByText("Weak fit")).toBeTruthy();
    expect(document.querySelector("meter")?.getAttribute("value")).toBe("64");
    expect(document.body.textContent).not.toMatch(/SENTINEL|"confidence":/);
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expectedCopy(output())));
    await waitFor(() => expect(made.calls.filter((c) => c.key === r.NEXT_ACTION)).toHaveLength(1));
    expect(JSON.parse(made.calls.find((c) => c.key === r.NEXT_ACTION)!.init.body as string)).toMatchObject({ checkpoint_id: "checkpoint_1" });
    expect(events.filter((e) => e.type === "scenario_completed")).toEqual([expect.objectContaining({ resultViewed: true })]);
    fireEvent.click(screen.getByRole("button", { name: "New task" }));
    expect((screen.getByLabelText("Task description") as HTMLTextAreaElement).value).toBe("");
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText("Task description")));
    expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
  });
  it("renders weak-input partial fit with an unspecified strengths list", async () => {
    const made = makeClientCapturingRequests(routes(output(".weak_input")));
    render(<TaskFinderProduct client={made.client} />); await submit();
    await waitFor(() => expect(screen.getByText("31 / 100")).toBeTruthy());
    expect(screen.getByText("Partial fit")).toBeTruthy(); expect(screen.getByText("Not specified.")).toBeTruthy();
  });
  it.each(["", " \n\t", "a".repeat(4001)])("rejects invalid form input without starting (case %#)", async (text) => {
    const made = makeClientCapturingRequests(routes()); render(<TaskFinderProduct client={made.client} />);
    await waitFor(() => expect((screen.getByRole("button", { name: "Check fit" }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(screen.getByLabelText("Task description"), { target: { value: text } });
    fireEvent.click(screen.getByRole("button", { name: "Check fit" }));
    expect(screen.getAllByRole("alert").length).toBeGreaterThan(0);
    expect(made.calls.some((c) => c.key === r.START)).toBe(false);
  });
  it("keeps the copied text English with Russian UI", async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "ru"); const copy = vi.fn(async () => true);
    render(<TaskFinderResultView result={parseTaskFinder(output())!} onCopy={copy} />);
    expect(screen.getByText("Низкое соответствие")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Скопировать" }));
    await waitFor(() => expect(copy).toHaveBeenCalledWith(expectedCopy(output())));
  });
  it.each(["failed", "invalid"])("shows safe failure for %s results", async (failure) => {
    const base = routes();
    if (failure === "failed") base[r.SESSION] = [sessionResponse({ status: "failed", result_artifact_id: null })];
    else base[r.RESULT] = [resultResponse(ids, { output: {} })];
    const made = makeClientCapturingRequests(base); render(<TaskFinderProduct client={made.client} />); await submit();
    await waitFor(() => expect(screen.getByText(TASK_FINDER_MESSAGES.en.fit.runFailed)).toBeTruthy());
    expect((screen.getByLabelText("Task description") as HTMLTextAreaElement).value).toBe("Build a dashboard.");
    expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
  });
  it("renders backend quota exhaustion", async () => {
    const made = makeClientCapturingRequests({ ...routes(), [r.START]: [errorResponse(429, "quota_exhausted")] });
    render(<TaskFinderProduct client={made.client} />); await submit();
    await waitFor(() => expect(screen.getByText(/used all your/)).toBeTruthy());
  });
});
