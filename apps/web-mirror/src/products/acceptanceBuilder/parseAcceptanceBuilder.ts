import { isRecord, isStringArray, isOneOf } from "../shared/resultGuards";
import { trimBackendWhitespace } from "../runtime/fieldValidation";
import { composeDocument } from "./presentation";
export { composeCopyText } from "./presentation";

// Acceptance Builder's canonical results (`acceptance_builder.draft_output_v1` / `check_output_v1`)
// as the page consumes them. The backend schema stays authoritative: this only checks the shapes
// and closed sets the renderer indexes into. The enum copies below are pinned by
// test/AcceptanceBuilderProduct.test.tsx against the schema files.

export const LIST_FIELDS = ["acceptance_criteria", "assumptions", "deliverables"] as const;
export const VERDICTS = ["meets_expectations", "partially_meets", "does_not_meet"] as const;
export const DELTA_STATUSES = ["match", "partial", "mismatch"] as const;
// Order is the schema's `prefixItems` order, which the copy text must follow.
export const DELTA_CRITERIA = ["scope_coverage", "requirement_fit", "completeness", "clarity"] as const;

export const LEVELS = ["low", "medium", "high"] as const;
export const ISSUE_CATEGORIES = [
  "missing_information",
  "ambiguity",
  "scope_risk",
  "timeline_risk",
  "budget_risk",
  "contradiction",
] as const;

type Level = (typeof LEVELS)[number];
export type IssueCategory = (typeof ISSUE_CATEGORIES)[number];

export type Issue = { category: IssueCategory; severity: Level; description: string; evidence?: string };
export type ClarifyingQuestion = { question: string; rationale: string; priority: Level; category: IssueCategory; sourceIssueIndex: number };
export type ListField = (typeof LIST_FIELDS)[number];
export type Verdict = (typeof VERDICTS)[number];
export type DeltaStatus = (typeof DELTA_STATUSES)[number];
export type DeltaCriterion = (typeof DELTA_CRITERIA)[number];

export type Delta = { criterionId: DeltaCriterion; status: DeltaStatus; evidence: string };
export type Comparison = { verdict: Verdict; deltas: Delta[]; rationale: string };
export type AcceptanceBuilderResult = {
  // A list the brief does not state is absent from `lists` and named in `missingFields`.
  lists: Partial<Record<ListField, string[]>>;
  analysisLanguage: string;
  missingFields: ListField[];
  // Deterministic presentation only; never an independent output.document.
  document: { sections: { title: string; content: string }[]; summary: string };
  // Present only for `check_v1`.
  comparison?: Comparison;
  issues?: Issue[];
  questions?: ClarifyingQuestion[];
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

export function hasAuthoredText(value: string): boolean {
  return trimBackendWhitespace(value.replaceAll("\ufeff", "")).length > 0;
}

// A stored Draft v1 used Python's whitespace set, which allowed a BOM on its own.
function isStoredText(value: unknown): value is string {
  return typeof value === "string" && trimBackendWhitespace(value).length > 0;
}

function toIssue(item: unknown): Issue | null {
  if (
    !isRecord(item) ||
    !isOneOf(ISSUE_CATEGORIES, item.category) ||
    !isOneOf(LEVELS, item.severity) ||
    !Object.keys(item).every((key) => ["category", "description", "severity", "evidence"].includes(key)) ||
    !isStoredText(item.description) ||
    (item.evidence !== undefined && !isStoredText(item.evidence))
  ) {
    return null;
  }
  return { category: item.category, severity: item.severity, description: item.description, evidence: item.evidence };
}

function toQuestion(item: unknown): ClarifyingQuestion | null {
  if (
    !isRecord(item) ||
    !Object.keys(item).every((key) => ["question", "rationale", "priority", "category", "source_issue_index"].includes(key)) ||
    typeof item.source_issue_index !== "number" || !Number.isInteger(item.source_issue_index) || item.source_issue_index < 0 ||
    !isStoredText(item.question) ||
    !isStoredText(item.rationale) ||
    !isOneOf(LEVELS, item.priority) ||
    !isOneOf(ISSUE_CATEGORIES, item.category)
  ) {
    return null;
  }
  return { question: item.question, rationale: item.rationale, priority: item.priority, category: item.category, sourceIssueIndex: item.source_issue_index };
}

function toLists(values: unknown): AcceptanceBuilderResult["lists"] | null {
  // `values` is a closed object with non-empty lists: an unknown key or an empty list is a
  // contract violation to reject, not something to drop or render as "stated".
  if (!isRecord(values) || !Object.keys(values).every((key) => isOneOf(LIST_FIELDS, key) || key === "analysis_language")) {
    return null;
  }
  const lists: AcceptanceBuilderResult["lists"] = {};
  for (const field of LIST_FIELDS) {
    const value = values[field];
    if (value === undefined) {
      continue;
    }
    if (!isStringArray(value) || value.length === 0) {
      return null;
    }
    lists[field] = value;
  }
  return lists;
}

function toDeltas(items: unknown): Delta[] | null {
  if (!Array.isArray(items) || items.length !== DELTA_CRITERIA.length) {
    return null;
  }
  const deltas: Delta[] = [];
  for (const [index, item] of items.entries()) {
    if (
      !isRecord(item) ||
      item.criterion_id !== DELTA_CRITERIA[index] ||
      !isOneOf(DELTA_STATUSES, item.status) ||
      typeof item.evidence !== "string"
    ) {
      return null;
    }
    deltas.push({ criterionId: DELTA_CRITERIA[index], status: item.status, evidence: item.evidence });
  }
  return deltas;
}

function toComparison(value: unknown): Comparison | null {
  if (!isRecord(value) || !isOneOf(VERDICTS, value.verdict) || typeof value.rationale !== "string") {
    return null;
  }
  const deltas = toDeltas(value.deltas);
  if (!deltas) return null;
  const expected = deltas.some((delta) => delta.status === "mismatch")
    ? "does_not_meet"
    : deltas.some((delta) => delta.status === "partial") ? "partially_meets" : "meets_expectations";
  return expected === value.verdict ? { verdict: expected, deltas, rationale: value.rationale } : null;
}

/** `requireComparison` is true for `check_v1`, whose output must carry a `comparison`. */
function extract(output: Record<string, unknown>, requireComparison: boolean): AcceptanceBuilderResult | null {
  const { extracted } = output;
  if (!isRecord(extracted) || !Array.isArray(extracted.missing_fields)) {
    return null;
  }
  const lists = toLists(extracted.values);
  const language = isRecord(extracted.values) ? extracted.values.analysis_language : undefined;
  if (typeof language !== "string" || !/^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$/.test(language)) return null;
  const missing = extracted.missing_fields;
  if (!lists || !missing.every((field): field is ListField => isOneOf(LIST_FIELDS, field))) {
    return null;
  }
  if (new Set(missing).size !== missing.length || LIST_FIELDS.some((field) => (lists[field] === undefined) !== missing.includes(field))) return null;
  // The draft output has no `comparison` (closed schema). An attached `?session=` id is editable, so
  // a check session must not be shown as a draft result with its verdict silently dropped.
  if (!requireComparison) {
    if (output.comparison !== undefined || Object.values(lists).some((items) => !items.every(isStoredText))) {
      return null;
    }
    const data = { lists, missingFields: missing, analysisLanguage: language };
    // Attached v1 results predate issue detection. Keep their lists readable without claiming a risk assessment.
    if (!("issues" in output) && !("questions" in output)) return { ...data, document: composeDocument(data) };
    const issues = mapAll(output.issues, toIssue);
    const questions = mapAll(output.questions, toQuestion);
    if (!issues || !questions || questions.length > 5 || questions.some((q) => q.sourceIssueIndex >= issues.length)) return null;
    const draft = { ...data, issues, questions };
    return { ...draft, document: composeDocument(draft) };
  }
  if ("issues" in output || "questions" in output) return null;
  const comparison = toComparison(output.comparison);
  if (!comparison) return null;
  const data = { lists, missingFields: missing, comparison, analysisLanguage: language };
  return { ...data, document: composeDocument(data) };
}

// `extracted.confidence` and `comparison.confidence` are deliberately not shown (like Brief Decoder's
// `brief.confidence`): a model self-estimate next to a rule-derived verdict invites false precision.
export const extractDraftResult = (output: Record<string, unknown>) => extract(output, false);
export const extractCheckResult = (output: Record<string, unknown>) => extract(output, true);

/** Activation for `draft_v1`: first display of a non-empty criteria list (no verdict exists). */
export function hasCriteria(result: AcceptanceBuilderResult): boolean {
  return result.lists.acceptance_criteria?.some(hasAuthoredText) ?? false;
}
