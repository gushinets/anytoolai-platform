import { expect, it } from "vitest";
import { LOCALES } from "../src/i18n";
import { proposalAiDefinition, type ProposalAIValues } from "../src/products/proposalAi/ProposalAIProduct";

const values: ProposalAIValues = { taskText: "\u0085Write a landing page.\u001f", freelancerPositioning: " I write landing pages. ", tone: "firm", language: "auto" };
const wire = proposalAiDefinition.toInput(values);

it.each(["auto", ...LOCALES] as const)("recovers normalized submitted values with %s language", (language) => {
  const submitted = { ...values, language };
  const input = proposalAiDefinition.toInput(submitted);
  const savedInput = structuredClone(input);
  const recovered = proposalAiDefinition.parseInputValues?.(input);
  expect(recovered).toEqual({ ...submitted, taskText: "Write a landing page.", freelancerPositioning: "I write landing pages." });
  expect(input).toEqual(savedInput);
  expect(proposalAiDefinition.toInput(recovered!)).toEqual(input);
});

it.each([
  null, [], "hello", {},
  { ...wire, result_contract: undefined },
  { ...wire, result_contract: null },
  { ...wire, result_contract: "unknown" },
  { ...wire, task_text: 42 },
  { ...wire, freelancer_positioning: null },
  { ...wire, task_text: "\u0085\u001f" },
  { ...wire, freelancer_positioning: " " },
  { ...wire, task_text: "a".repeat(4001) },
  { ...wire, freelancer_positioning: "a".repeat(4001) },
  { ...wire, tone: "unknown" },
  { ...wire, tone: undefined },
  { ...wire, language: null },
  { ...wire, language: "auto" },
  { ...wire, language: "en-US" },
  { ...wire, extra: "unsupported" },
])("rejects unsupported frozen input without inventing form values: %j", (input) => {
  expect(proposalAiDefinition.parseInputValues?.(input)).toBeNull();
});

it("counts Unicode code points consistently with submission validation", () => {
  const input = { ...wire, task_text: "🙂".repeat(4000) };
  expect(proposalAiDefinition.parseInputValues?.(input)?.taskText).toBe(input.task_text);
});
