// Brief Decoder's canonical result (`brief_decoder.decode_output_v1`) as the page consumes it.
// The backend schema stays authoritative: this only checks the shapes and closed sets the renderer
// indexes into, not the 4-section tuple or `questions.maxItems`. `BRIEF_FIELDS`/`LEVELS`/
// `ISSUE_CATEGORIES` are copies of the schema's enums, pinned by test/BriefDecoderProduct.test.tsx.

export const BRIEF_FIELDS = ["project_goal", "deliverables", "deadline", "budget", "target_audience", "constraints"] as const;
export const LEVELS = ["low", "medium", "high"] as const;
export const ISSUE_CATEGORIES = [
  "missing_information",
  "ambiguity",
  "scope_risk",
  "timeline_risk",
  "budget_risk",
  "contradiction",
] as const;

type BriefField = (typeof BRIEF_FIELDS)[number];
type Level = (typeof LEVELS)[number];
export type IssueCategory = (typeof ISSUE_CATEGORIES)[number];

export type BriefIssue = { category: IssueCategory; severity: Level; description: string; evidence?: string };
export type ClarifyingQuestion = { question: string; rationale: string; priority: Level; category: IssueCategory };
export type BriefDecoderResult = {
  // Fields the brief does not state are simply absent from `values` (rendered as "not provided").
  brief: { values: Partial<Record<BriefField, string | string[]>> };
  issues: BriefIssue[];
  questions: ClarifyingQuestion[];
  document: { sections: { title: string; content: string }[]; summary: string };
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isOneOf<T extends string>(set: readonly T[], value: unknown): value is T {
  return typeof value === "string" && (set as readonly string[]).includes(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

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
  const issues = mapAll(output.issues, toIssue);
  const questions = mapAll(output.questions, toQuestion);
  const sections = mapAll(document.sections, toSection);
  if (!issues || !questions || !sections) {
    return null;
  }
  return {
    brief: { values },
    issues,
    questions,
    document: { sections, summary: document.summary },
  };
}

/** Python `re` `\s` (the backend's `brief_text` pattern) for a str: Unicode White_Space-ish set plus
 * U+001C-U+001F and U+0085, and *not* U+FEFF. JS `trim()` differs on exactly those code points, so
 * the client must not use it for this field. */
const BACKEND_WHITESPACE = "\\t\\n\\v\\f\\r \\u001c-\\u001f\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const OUTER_BACKEND_WHITESPACE = new RegExp(`^[${BACKEND_WHITESPACE}]+|[${BACKEND_WHITESPACE}]+$`, "g");

/** The brief exactly as the backend accepts it: outer whitespace removed, inner text untouched. */
export function trimBriefText(value: string): string {
  return value.replace(OUTER_BACKEND_WHITESPACE, "");
}

/** `renderer_contract.yaml`'s `canonical_field_composition`: each section as a title line then its
 * content, sections separated by one blank line, then one more blank line and the summary. */
export function composeCopyText({ sections, summary }: BriefDecoderResult["document"]): string {
  return [...sections.map((section) => `${section.title}\n${section.content}`), summary].join("\n\n");
}

/** Activation = first rendering of a non-empty clarifying-question list. */
export function hasQuestions(result: BriefDecoderResult): boolean {
  return result.questions.length > 0;
}
