import { hasAuthoredText } from "../shared/authoredText";
import outputWording from "./outputWording.json";
import {
  LIST_FIELDS,
  type AcceptanceBuilderResult,
  type DeltaCriterion,
  type DeltaStatus,
  type IssueCategory,
  type ListField,
  type Verdict,
} from "./parseAcceptanceBuilder";

type Words = {
  verdicts: Readonly<Record<Verdict, string>>;
  statuses: Readonly<Record<DeltaStatus, string>>;
  criteria: Readonly<Record<DeltaCriterion, string>>;
  lists: Readonly<Record<ListField, string>>;
  verdict: string;
  gaps: string;
  missing: string;
  complete: string;
  risks: string;
  questions: string;
  partial: string;
  unavailable: string;
  noRisks: string;
  noQuestions: string;
  listsPresent: string;
  evidence: string;
  categories: Readonly<Record<IssueCategory, string>>;
  confirm: string;
};

// These are output-language words, never UI-locale messages.
export const WORDS: Readonly<Record<string, Words>> = outputWording;

// Unsupported analysis languages retain the original prose and use neutral labels.
const NEUTRAL: Words = {
  verdicts: {
    meets_expectations: "✓",
    partially_meets: "△",
    does_not_meet: "✗",
    insufficient_brief: "?"
  },
  statuses: {
    match: "✓",
    partial: "△",
    mismatch: "✗"
  },
  criteria: {
    scope_coverage: "scope_coverage",
    requirement_fit: "requirement_fit",
    completeness: "completeness",
    clarity: "clarity"
  },
  lists: {
    acceptance_criteria: "acceptance_criteria",
    assumptions: "assumptions",
    deliverables: "deliverables"
  },
  verdict: "verdict",
  gaps: "missing_fields",
  missing: "—",
  risks: "issues",
  questions: "questions",
  partial: "⚠",
  unavailable: "[…]",
  noRisks: "✓",
  noQuestions: "—",
  listsPresent: "✓",
  evidence: "«»",
  categories: {
    missing_information: "missing_information",
    ambiguity: "ambiguity",
    scope_risk: "scope_risk",
    timeline_risk: "timeline_risk",
    budget_risk: "budget_risk",
    contradiction: "contradiction"
  },
  complete: "✓",
  confirm: "?"
};

type StructuredResult = Pick<AcceptanceBuilderResult, "lists" | "missingFields" | "comparison" | "analysisLanguage" | "issues" | "questions">;

export function composeDocument(result: StructuredResult): AcceptanceBuilderResult["document"] {
  const words = WORDS[result.analysisLanguage.split("-")[0].toLowerCase()] ?? NEUTRAL;
  const sections: { title: string; content: string }[] = [];
  let summary = "";
  let partial = false;
  function display(text: string): string {
    if (result.comparison || hasAuthoredText(text)) return text;
    partial = true;
    return words.unavailable;
  }
  if (result.comparison) {
    const { verdict, deltas, rationale } = result.comparison;
    summary = `${words.verdict}: ${words.verdicts[verdict]}.`;
    const evidence = deltas.map((delta) =>
      `${words.criteria[delta.criterionId]}: ${words.statuses[delta.status]}. ${delta.evidence}`
    );
    sections.push({ title: words.verdict, content: [summary, ...evidence, rationale].join("\n") });
  }
  for (const field of LIST_FIELDS) {
    sections.push({
      title: words.lists[field],
      content: result.lists[field]?.map((item) => `- ${display(item)}`).join("\n") ?? words.missing
    });
  }
  const listSummary = partial ? words.unavailable : (result.comparison ? words.complete : words.listsPresent);
  const gapLines = result.missingFields.map((field) =>
    `- ${words.lists[field].toLowerCase()}: ${words.confirm}.`
  );
  if (result.issues && result.questions) {
    const riskLines: string[] = [];
    for (const issue of result.issues) {
      const label = words.categories[issue.category];
      const evidence = issue.evidence ? `\n  ${words.evidence}: ${display(issue.evidence)}` : "";
      const line = `- ${label}: ${display(issue.description)}${evidence}`;
      const lines = issue.category === "missing_information" ? gapLines : riskLines;
      lines.push(line);
    }
    const questions = result.questions.map((item, index) => {
      if (!hasAuthoredText(item.rationale)) partial = true;
      return `${index + 1}. ${display(item.question)}`;
    });
    sections.push({ title: words.risks, content: riskLines.join("\n") || words.noRisks });
    sections.push({ title: words.questions, content: questions.join("\n") || words.noQuestions });
    if (riskLines.length) summary = `${words.risks}: ${riskLines.length}`;
    else if (questions.length) summary = `${words.questions}: ${questions.length}`;
  }
  const gapText = gapLines.join("\n") || listSummary;
  if (!summary) summary = gapText;
  sections.push({ title: words.gaps, content: gapText });
  if (partial) {
    summary = words.partial;
    sections.unshift({ title: words.partial, content: words.unavailable });
  }
  return { summary, sections };
}

export function composeCopyText(result: StructuredResult): string {
  return composeDocument(result).sections.map(({ title, content }) => `${title}\n${content}`).join("\n\n");
}
