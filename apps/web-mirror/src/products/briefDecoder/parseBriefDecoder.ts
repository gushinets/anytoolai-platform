import { hasAuthoredText } from "../shared/authoredText";
import type { Translate } from "../../i18n";
import { isRecord, isStringArray, isOneOf } from "../shared/resultGuards";

// Brief Decoder's canonical result (`brief_decoder.decode_output_v1`) as the page consumes it.
// The backend schema stays authoritative: this only checks the shapes and closed sets the renderer
// indexes into, including missing_fields for copy, not the 4-section tuple or `questions.maxItems`.
// `BRIEF_FIELDS`/`LEVELS`/`ISSUE_CATEGORIES` mirror schema enums, pinned by test/BriefDecoderProduct.test.tsx.

export const BRIEF_FIELDS = ["project_goal", "deliverables", "deadline", "budget", "target_audience", "constraints"] as const;
export const LEVELS = ["low", "medium", "high"] as const;
export const ISSUE_CATEGORIES = [
  "missing_information",
  "ambiguity",
  "scope_risk",
  "timeline_risk",
  "budget_risk",
  "contradiction",
  "missing_task_description",
] as const;

export type BriefField = (typeof BRIEF_FIELDS)[number];
type Level = (typeof LEVELS)[number];
export type IssueCategory = (typeof ISSUE_CATEGORIES)[number];

export type BriefIssue = { category: IssueCategory; severity: Level; description: string; evidence?: string };
export type ClarifyingQuestion = { question: string; rationale: string; priority: Level; category: IssueCategory };
export type BriefDecoderResult = {
  // Fields the brief does not state are simply absent from `values` (rendered as "not provided").
  brief: { values: Partial<Record<BriefField, string | string[]>>; missingFields: BriefField[] };
  issues: BriefIssue[];
  questions: ClarifyingQuestion[];
  // Display only; copy is built from the structured fields.
  document: { sections: { title: string; content: string }[]; summary: string };
};

function mapAll<T>(items: unknown, map: (item: unknown) => T | null): T[] | null {
  if (!Array.isArray(items)) {
    return null;
  }
  const out: T[] = [];
  for (const item of items) {
    const mapped = map(item);
    if (mapped === null) {
      return null;
    }
    out.push(mapped);
  }
  return out;
}

function toIssue(item: unknown): BriefIssue | null {
  if (
    !isRecord(item) ||
    !isOneOf(ISSUE_CATEGORIES, item.category) ||
    !isOneOf(LEVELS, item.severity) ||
    typeof item.description !== "string" ||
    (item.evidence !== undefined && typeof item.evidence !== "string")
  ) {
    return null;
  }
  return { category: item.category, severity: item.severity, description: item.description, evidence: item.evidence };
}

function toQuestion(item: unknown): ClarifyingQuestion | null {
  if (
    !isRecord(item) ||
    typeof item.question !== "string" ||
    typeof item.rationale !== "string" ||
    !isOneOf(LEVELS, item.priority) ||
    !isOneOf(ISSUE_CATEGORIES, item.category)
  ) {
    return null;
  }
  return { question: item.question, rationale: item.rationale, priority: item.priority, category: item.category };
}

function toSection(item: unknown): { title: string; content: string } | null {
  return isRecord(item) && typeof item.title === "string" && typeof item.content === "string"
    ? { title: item.title, content: item.content }
    : null;
}

export function extractBriefDecoderResult(output: Record<string, unknown>): BriefDecoderResult | null {
  const { brief, document } = output;
  if (!isRecord(brief) || !isRecord(brief.values) || !isRecord(document) || typeof document.summary !== "string") {
    return null;
  }
  // `brief.values` is a closed object in the schema (`additionalProperties: false`): an unknown key
  // is a contract violation to reject, not something to drop silently.
  if (!Object.keys(brief.values).every((key) => isOneOf(BRIEF_FIELDS, key))) {
    return null;
  }
  const values: BriefDecoderResult["brief"]["values"] = {};
  for (const field of BRIEF_FIELDS) {
    const value = brief.values[field];
    if (value === undefined) {
      continue;
    }
    if (typeof value !== "string" && !isStringArray(value)) {
      return null;
    }
    values[field] = value;
  }
  const missingFields = BRIEF_FIELDS.filter((field) => values[field] === undefined);
  const rawMissingFields = brief.missing_fields;
  // Supplied metadata must list each absent field exactly once.
  if (rawMissingFields !== undefined && (
    !Array.isArray(rawMissingFields) ||
    rawMissingFields.length !== missingFields.length ||
    !missingFields.every((field) => rawMissingFields.includes(field))
  )) {
    return null;
  }
  const issues = mapAll(output.issues, toIssue);
  const questions = mapAll(output.questions, toQuestion);
  const sections = mapAll(document.sections, toSection);
  if (!issues || !questions || !sections) {
    return null;
  }
  return {
    brief: { values, missingFields },
    issues,
    questions,
    document: { sections, summary: document.summary },
  };
}

type CopySource = Pick<BriefDecoderResult, "brief" | "issues" | "questions">;

/** Copy structured content verbatim; labels use the UI locale because the result has no analysis language. */
export function composeCopyText({ brief, issues, questions }: CopySource, t: Translate): string {
  const briefLines = [t("result.brief")];
  for (const field of BRIEF_FIELDS) {
    const value = brief.values[field];
    if (value === undefined) continue;
    if (Array.isArray(value)) {
      briefLines.push(`${t(`briefFields.${field}`)}:`, ...value.map((item) => `- ${item}`));
    } else {
      briefLines.push(`${t(`briefFields.${field}`)}: ${value}`);
    }
  }
  const blocks = [briefLines.join("\n")];
  if (brief.missingFields.length > 0) {
    blocks.push([t("copy.missingFields"), ...brief.missingFields.map((field) => `- ${t(`briefFields.${field}`)}`)].join("\n"));
  }
  const issueLines = issues.length === 0
    ? [t("result.noIssues")]
    : issues.flatMap((issue) => [
        `- ${t(`categories.${issue.category}`)} · ${t(`severity.${issue.severity}`)}: ${issue.description}`,
        ...(issue.evidence ? [`  ${t("result.evidence", { text: issue.evidence })}`] : []),
      ]);
  blocks.push([t("result.issues"), ...issueLines].join("\n"));
  const questionLines = questions.length === 0
    ? [t("result.noQuestions")]
    : questions.map((question, index) => `${index + 1}. ${question.question}`);
  blocks.push([t("result.questions", { count: questions.length }), ...questionLines].join("\n"));
  return blocks.join("\n\n");
}

/** Activation = first rendering of a non-empty clarifying-question list. */
export function hasQuestions(result: BriefDecoderResult): boolean {
  return result.questions.some(({ question }) => hasAuthoredText(question));
}
