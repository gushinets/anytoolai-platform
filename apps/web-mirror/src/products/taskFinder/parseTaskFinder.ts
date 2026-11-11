import { isRecord, isStringArray } from "../shared/resultGuards";

// Backend schemas own validation; this boundary checks the fields and closed sets the UI consumes.
export const CRITERIA = {
  skills_fit: "Skills fit",
  experience_fit: "Experience fit",
  scope_fit: "Scope fit",
  constraints_fit: "Constraints fit",
} as const;
export const VERDICTS = { strong_fit: "strong fit", partial_fit: "partial fit", weak_fit: "weak fit" } as const;
export const STATUSES = { match: true, partial: true, mismatch: true } as const;
export type Criterion = keyof typeof CRITERIA;
export type Verdict = keyof typeof VERDICTS;
export type Delta = { criterionId: Criterion; status: keyof typeof STATUSES; evidence: string };
export type CriterionScore = { criterionId: Criterion; score: number; rationale: string };
export type TaskFinderResult = {
  verdict: Verdict;
  deltas: Delta[];
  rationale: string;
  criterionScores: CriterionScore[];
  score: number;
  strengths: string[];
  gaps: string[];
  scoreRationale: string;
};
export const CRITERION_ORDER = Object.keys(CRITERIA) as Criterion[];

function member<T extends object>(set: T, value: unknown): value is keyof T & string {
  return typeof value === "string" && Object.hasOwn(set, value);
}
function score(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100;
}

export function parseTaskFinder(output: Record<string, unknown>): TaskFinderResult | null {
  const { comparison, match } = output;
  if (!isRecord(comparison) || !isRecord(match) || !member(VERDICTS, comparison.verdict) ||
      typeof comparison.rationale !== "string" || typeof match.overall_rationale !== "string" ||
      !score(match.score) || !isStringArray(match.strengths) || !isStringArray(match.gaps) ||
      !Array.isArray(comparison.deltas) || comparison.deltas.length !== CRITERION_ORDER.length ||
      !Array.isArray(match.criterion_scores) || match.criterion_scores.length !== CRITERION_ORDER.length) {
    return null;
  }
  const deltas = new Map<Criterion, Delta>();
  for (const item of comparison.deltas) {
    if (!isRecord(item) || !member(CRITERIA, item.criterion_id) || deltas.has(item.criterion_id) ||
        !member(STATUSES, item.status) || typeof item.evidence !== "string") return null;
    deltas.set(item.criterion_id, { criterionId: item.criterion_id, status: item.status, evidence: item.evidence });
  }
  const scores = new Map<Criterion, CriterionScore>();
  for (const item of match.criterion_scores) {
    if (!isRecord(item) || !member(CRITERIA, item.criterion_id) || scores.has(item.criterion_id) ||
        !score(item.score) || typeof item.rationale !== "string") return null;
    scores.set(item.criterion_id, { criterionId: item.criterion_id, score: item.score, rationale: item.rationale });
  }
  // Exact lengths plus unique closed ids guarantee all four entries. Echoes and confidence stay out.
  return {
    verdict: comparison.verdict, rationale: comparison.rationale,
    deltas: CRITERION_ORDER.map((id) => deltas.get(id)!),
    criterionScores: CRITERION_ORDER.map((id) => scores.get(id)!),
    score: match.score, strengths: match.strengths, gaps: match.gaps, scoreRationale: match.overall_rationale,
  };
}

/** Fixed English per renderer_contract.yaml, independent of the interface language. */
export function composeCopyText(result: TaskFinderResult): string {
  return [
    `Fit\nFit score: ${result.score}/100. ${result.scoreRationale}\nVerdict: ${VERDICTS[result.verdict]}. ${result.rationale}`,
    `Criteria\n${result.deltas.map((d) => `${CRITERIA[d.criterionId]}: ${d.status}. ${d.evidence}`).join("\n")}`,
    `Criterion scores\n${result.criterionScores.map((s) => `${CRITERIA[s.criterionId]}: ${s.score}/100. ${s.rationale}`).join("\n")}`,
    `Strengths\n${result.strengths.length ? result.strengths.map((s) => `- ${s}`).join("\n") : "Not specified."}`,
    `Gaps\n${result.gaps.length ? result.gaps.map((s) => `- ${s}`).join("\n") : "Not specified."}`,
  ].join("\n\n");
}
