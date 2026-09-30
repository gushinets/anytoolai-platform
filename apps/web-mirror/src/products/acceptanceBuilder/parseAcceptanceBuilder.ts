// Acceptance Builder's canonical results (`acceptance_builder.draft_output_v1` / `check_output_v1`)
// as the page consumes them. The backend schema stays authoritative: this only checks the shapes
// and closed sets the renderer indexes into. The enum copies below are pinned by
// test/AcceptanceBuilderProduct.test.tsx against the schema files.

export const LIST_FIELDS = ["acceptance_criteria", "assumptions", "deliverables"] as const;
export const VERDICTS = ["meets_expectations", "partially_meets", "does_not_meet"] as const;
export const DELTA_STATUSES = ["match", "partial", "mismatch"] as const;
// Order is the schema's `prefixItems` order, which the copy text must follow.
export const DELTA_CRITERIA = ["scope_coverage", "requirement_fit", "completeness", "clarity"] as const;

export type ListField = (typeof LIST_FIELDS)[number];
export type Verdict = (typeof VERDICTS)[number];
export type DeltaStatus = (typeof DELTA_STATUSES)[number];
export type DeltaCriterion = (typeof DELTA_CRITERIA)[number];

export type Delta = { criterionId: DeltaCriterion; status: DeltaStatus; evidence: string };
export type Comparison = { verdict: Verdict; deltas: Delta[]; rationale: string };
export type AcceptanceBuilderResult = {
  // A list the brief does not state is absent from `lists` and named in `missingFields`.
  lists: Partial<Record<ListField, string[]>>;
  missingFields: ListField[];
  document: { sections: { title: string; content: string }[]; summary: string };
  // Present only for `check_v1`.
  comparison?: Comparison;
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

function toLists(values: unknown): AcceptanceBuilderResult["lists"] | null {
  // `values` is a closed object with non-empty lists: an unknown key or an empty list is a
  // contract violation to reject, not something to drop or render as "stated".
  if (!isRecord(values) || !Object.keys(values).every((key) => isOneOf(LIST_FIELDS, key))) {
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
  return deltas ? { verdict: value.verdict, deltas, rationale: value.rationale } : null;
}

function toDocument(value: unknown): AcceptanceBuilderResult["document"] | null {
  if (!isRecord(value) || typeof value.summary !== "string" || !Array.isArray(value.sections)) {
    return null;
  }
  const sections: { title: string; content: string }[] = [];
  for (const section of value.sections) {
    if (!isRecord(section) || typeof section.title !== "string" || typeof section.content !== "string") {
      return null;
    }
    sections.push({ title: section.title, content: section.content });
  }
  return { sections, summary: value.summary };
}

/** `requireComparison` is true for `check_v1`, whose output must carry a `comparison`. */
function extract(output: Record<string, unknown>, requireComparison: boolean): AcceptanceBuilderResult | null {
  const { extracted } = output;
  if (!isRecord(extracted) || !Array.isArray(extracted.missing_fields)) {
    return null;
  }
  const lists = toLists(extracted.values);
  const document = toDocument(output.document);
  const missing = extracted.missing_fields;
  if (!lists || !document || !missing.every((field): field is ListField => isOneOf(LIST_FIELDS, field))) {
    return null;
  }
  // The draft output has no `comparison` (closed schema). An attached `?session=` id is editable, so
  // a check session must not be shown as a draft result with its verdict silently dropped.
  if (!requireComparison) {
    if (output.comparison !== undefined) {
      return null;
    }
    return { lists, missingFields: missing, document };
  }
  const comparison = toComparison(output.comparison);
  return comparison ? { lists, missingFields: missing, document, comparison } : null;
}

// `extracted.confidence` and `comparison.confidence` are deliberately not shown (like Brief Decoder's
// `brief.confidence`): a model self-estimate next to a rule-derived verdict invites false precision.
export const extractDraftResult = (output: Record<string, unknown>) => extract(output, false);
export const extractCheckResult = (output: Record<string, unknown>) => extract(output, true);

const VERDICT_WORDS: Record<Verdict, string> = {
  meets_expectations: "meets expectations",
  partially_meets: "partially meets expectations",
  does_not_meet: "does not meet expectations",
};
const DELTA_LABELS: Record<DeltaCriterion, string> = {
  scope_coverage: "Scope coverage",
  requirement_fit: "Requirement fit",
  completeness: "Completeness",
  clarity: "Clarity",
};
const LIST_TITLES: Record<ListField, string> = {
  acceptance_criteria: "Acceptance criteria",
  assumptions: "Assumptions",
  deliverables: "Deliverables",
};
const GAP_NAMES: Record<ListField, string> = {
  acceptance_criteria: "acceptance criteria",
  assumptions: "assumptions",
  deliverables: "deliverables",
};
const NOT_SPECIFIED = "Not specified in the brief.";
const ALL_STATED = "The brief states all three lists.";

/** `renderer_contract.yaml`'s `copy_text`, verbatim: the text the freelancer sends on to a client
 * is fixed English, not UI-locale copy, and is built from the structured fields only (never from
 * `document`). Blocks are a title line then a body, separated by one blank line. */
export function composeCopyText({ comparison, lists, missingFields }: AcceptanceBuilderResult): string {
  const blocks: string[] = [];
  if (comparison) {
    const deltaLines = comparison.deltas.map(
      (delta) => `${DELTA_LABELS[delta.criterionId]}: ${delta.status}. ${delta.evidence}`,
    );
    const body = [`Verdict: ${VERDICT_WORDS[comparison.verdict]}.`, ...deltaLines, comparison.rationale];
    blocks.push(`Verdict\n${body.join("\n")}`);
  }
  for (const field of LIST_FIELDS) {
    const items = lists[field];
    blocks.push(`${LIST_TITLES[field]}\n${items ? items.map((item) => `- ${item}`).join("\n") : NOT_SPECIFIED}`);
  }
  const gaps =
    missingFields.length === 0
      ? ALL_STATED
      : missingFields.map((field) => `- ${GAP_NAMES[field]}: the client should confirm it.`).join("\n");
  blocks.push(`Open gaps\n${gaps}`);
  return blocks.join("\n\n");
}

/** Activation for `draft_v1`: first display of a non-empty criteria list (no verdict exists). */
export function hasCriteria(result: AcceptanceBuilderResult): boolean {
  return (result.lists.acceptance_criteria?.length ?? 0) > 0;
}
