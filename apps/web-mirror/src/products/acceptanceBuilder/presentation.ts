import {
  DELTA_CRITERIA, DELTA_STATUSES, LIST_FIELDS, VERDICTS, type AcceptanceBuilderResult
} from "./parseAcceptanceBuilder";

type Words = {
  verdicts: readonly [string, string, string];
  statuses: readonly [string, string, string];
  criteria: readonly [string, string, string, string];
  lists: readonly [string, string, string];
  verdict: string;
  gaps: string;
  missing: string;
  complete: string;
  confirm: string;
};

// These are output-language words, never UI-locale messages.
export const WORDS: Readonly<Record<string, Words>> = {
  en: {
    verdicts: ["meets expectations", "partially meets expectations", "does not meet expectations"],
    statuses: ["match", "partial", "mismatch"],
    criteria: ["Scope coverage", "Requirement fit", "Completeness", "Clarity"],
    lists: ["Acceptance criteria", "Assumptions", "Deliverables"],
    verdict: "Verdict",
    gaps: "Open gaps",
    missing: "Not specified in the brief.",
    complete: "The brief states all three lists.",
    confirm: "the client should confirm it"
  },
  ru: {
    verdicts: ["соответствует ожиданиям", "частично соответствует ожиданиям", "не соответствует ожиданиям"],
    statuses: ["выполнено", "частично выполнено", "не выполнено"],
    criteria: ["Охват объёма работ", "Соответствие требованиям", "Полнота", "Ясность"],
    lists: ["Критерии приёмки", "Допущения", "Результаты работы"],
    verdict: "Вердикт",
    gaps: "Открытые вопросы",
    missing: "Не указано в брифе.",
    complete: "В брифе указаны все три списка.",
    confirm: "клиенту следует подтвердить"
  },
  es: {
    verdicts: ["cumple las expectativas", "cumple parcialmente las expectativas", "no cumple las expectativas"],
    statuses: ["cumplido", "parcialmente cumplido", "no cumplido"],
    criteria: ["Cobertura del alcance", "Adecuación a los requisitos", "Integridad", "Claridad"],
    lists: ["Criterios de aceptación", "Supuestos", "Entregables"],
    verdict: "Veredicto",
    gaps: "Cuestiones pendientes",
    missing: "No se especifica en el encargo.",
    complete: "El encargo especifica las tres listas.",
    confirm: "el cliente debe confirmarlo"
  },
  de: {
    verdicts: ["erfüllt die Erwartungen", "erfüllt die Erwartungen teilweise", "erfüllt die Erwartungen nicht"],
    statuses: ["erfüllt", "teilweise erfüllt", "nicht erfüllt"],
    criteria: ["Umfang", "Anforderungserfüllung", "Vollständigkeit", "Klarheit"],
    lists: ["Abnahmekriterien", "Annahmen", "Liefergegenstände"],
    verdict: "Urteil",
    gaps: "Offene Fragen",
    missing: "Im Briefing nicht angegeben.",
    complete: "Das Briefing enthält alle drei Listen.",
    confirm: "vom Kunden zu bestätigen"
  },
  fr: {
    verdicts: ["répond aux attentes", "répond partiellement aux attentes", "ne répond pas aux attentes"],
    statuses: ["satisfait", "partiellement satisfait", "non satisfait"],
    criteria: ["Couverture du périmètre", "Conformité aux exigences", "Exhaustivité", "Clarté"],
    lists: ["Critères d’acceptation", "Hypothèses", "Livrables"],
    verdict: "Verdict",
    gaps: "Questions ouvertes",
    missing: "Non précisé dans le brief.",
    complete: "Le brief précise les trois listes.",
    confirm: "à confirmer par le client"
  },
  it: {
    verdicts: ["soddisfa le aspettative", "soddisfa parzialmente le aspettative", "non soddisfa le aspettative"],
    statuses: ["soddisfatto", "parzialmente soddisfatto", "non soddisfatto"],
    criteria: ["Copertura dell’ambito", "Conformità ai requisiti", "Completezza", "Chiarezza"],
    lists: ["Criteri di accettazione", "Presupposti", "Risultati da consegnare"],
    verdict: "Verdetto",
    gaps: "Questioni aperte",
    missing: "Non specificato nel brief.",
    complete: "Il brief specifica tutti e tre gli elenchi.",
    confirm: "da confermare con il cliente"
  },
  pt: {
    verdicts: ["cumpre as expectativas", "cumpre parcialmente as expectativas", "não cumpre as expectativas"],
    statuses: ["cumprido", "parcialmente cumprido", "não cumprido"],
    criteria: ["Cobertura do âmbito", "Adequação aos requisitos", "Completude", "Clareza"],
    lists: ["Critérios de aceitação", "Pressupostos", "Entregáveis"],
    verdict: "Veredicto",
    gaps: "Questões em aberto",
    missing: "Não especificado no briefing.",
    complete: "O briefing especifica as três listas.",
    confirm: "a confirmar pelo cliente"
  },
};

// shortcut: other languages use neutral markers; add wording when localization is needed.
const NEUTRAL: Words = {
  verdicts: ["✓", "△", "✗"],
  statuses: ["✓", "△", "✗"],
  criteria: ["scope_coverage", "requirement_fit", "completeness", "clarity"],
  lists: ["acceptance_criteria", "assumptions", "deliverables"],
  verdict: "verdict",
  gaps: "missing_fields",
  missing: "—",
  complete: "✓",
  confirm: "?"
};
type StructuredResult = Pick<AcceptanceBuilderResult, "lists" | "missingFields" | "comparison" | "analysisLanguage">;

export function composeDocument(result: StructuredResult): AcceptanceBuilderResult["document"] {
  const words = WORDS[result.analysisLanguage.split("-")[0]] ?? NEUTRAL;
  const sections: { title: string; content: string }[] = [];
  let summary = words.complete;
  if (result.comparison) {
    const { verdict, deltas, rationale } = result.comparison;
    summary = `${words.verdict}: ${words.verdicts[VERDICTS.indexOf(verdict)]}.`;
    const evidence = deltas.map((delta) =>
      `${words.criteria[DELTA_CRITERIA.indexOf(delta.criterionId)]}: ${words.statuses[DELTA_STATUSES.indexOf(delta.status)]}. ${delta.evidence}`
    );
    sections.push({ title: words.verdict, content: [summary, ...evidence, rationale].join("\n") });
  }
  for (const [index, field] of LIST_FIELDS.entries()) {
    sections.push({
      title: words.lists[index],
      content: result.lists[field]?.map((item) => `- ${item}`).join("\n") ?? words.missing
    });
  }
  const gaps = result.missingFields.map((field) =>
    `- ${words.lists[LIST_FIELDS.indexOf(field)].toLowerCase()}: ${words.confirm}.`
  ).join("\n");
  sections.push({ title: words.gaps, content: gaps || words.complete });
  if (!result.comparison) summary = gaps || words.complete;
  return { summary, sections };
}

export function composeCopyText(result: StructuredResult): string {
  return composeDocument(result).sections.map(({ title, content }) => `${title}\n${content}`).join("\n\n");
}
