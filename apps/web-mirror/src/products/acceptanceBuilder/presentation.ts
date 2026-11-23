import {
  ISSUE_CATEGORIES, DELTA_CRITERIA, DELTA_STATUSES, LIST_FIELDS, VERDICTS, type AcceptanceBuilderResult
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
  risks: string;
  questions: string;
  noRisks: string;
  noQuestions: string;
  listsPresent: string;
  evidence: string;
  categories: readonly [string, string, string, string, string, string];
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
    risks: "Risks and contradictions",
    questions: "Questions for the client",
    noRisks: "No risks or contradictions detected in the brief.",
    noQuestions: "No clarifying questions.",
    listsPresent: "Each of the three lists has at least one item in the brief.",
    evidence: "From the brief",
    categories: ["Missing information", "Ambiguity", "Scope risk", "Timeline risk", "Budget risk", "Contradiction"],
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
    risks: "Риски и противоречия",
    questions: "Вопросы клиенту",
    noRisks: "Рисков и противоречий в брифе не обнаружено.",
    noQuestions: "Уточняющих вопросов нет.",
    listsPresent: "Каждый из трёх списков содержит хотя бы один пункт из брифа.",
    evidence: "Из брифа",
    categories: ["Не хватает сведений", "Неоднозначность", "Риск объёма работ", "Риск по срокам", "Риск по бюджету", "Противоречие"],
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
    risks: "Riesgos y contradicciones",
    questions: "Preguntas para el cliente",
    noRisks: "No se han detectado riesgos ni contradicciones en el encargo.",
    noQuestions: "No hay preguntas pendientes de aclaración.",
    listsPresent: "Cada lista contiene al menos un elemento del encargo.",
    evidence: "Del encargo",
    categories: ["Falta de información", "Ambigüedad", "Riesgo de alcance", "Riesgo de plazo", "Riesgo presupuestario", "Contradicción"],
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
    risks: "Risiken und Widersprüche",
    questions: "Fragen an den Kunden",
    noRisks: "Im Briefing wurden keine Risiken oder Widersprüche erkannt.",
    noQuestions: "Keine Rückfragen.",
    listsPresent: "Jede der drei Listen enthält mindestens einen Punkt aus dem Briefing.",
    evidence: "Aus dem Briefing",
    categories: ["Fehlende Angaben", "Mehrdeutigkeit", "Umfangsrisiko", "Terminrisiko", "Budgetrisiko", "Widerspruch"],
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
    risks: "Risques et contradictions",
    questions: "Questions au client",
    noRisks: "Aucun risque ni aucune contradiction détectés dans le brief.",
    noQuestions: "Aucune question à clarifier.",
    listsPresent: "Chaque liste contient au moins un élément du brief.",
    evidence: "Extrait du brief",
    categories: ["Informations manquantes", "Ambiguïté", "Risque lié au périmètre", "Risque de délai", "Risque budgétaire", "Contradiction"],
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
    risks: "Rischi e contraddizioni",
    questions: "Domande per il cliente",
    noRisks: "Nel brief non sono stati rilevati rischi o contraddizioni.",
    noQuestions: "Nessuna domanda di chiarimento.",
    listsPresent: "Ciascun elenco contiene almeno un elemento del brief.",
    evidence: "Dal brief",
    categories: ["Informazioni mancanti", "Ambiguità", "Rischio relativo all’ambito", "Rischio sui tempi", "Rischio di budget", "Contraddizione"],
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
    risks: "Riscos e contradições",
    questions: "Perguntas ao cliente",
    noRisks: "Não foram detetados riscos nem contradições no briefing.",
    noQuestions: "Não há perguntas de esclarecimento.",
    listsPresent: "Cada lista contém pelo menos um elemento do briefing.",
    evidence: "Do briefing",
    categories: ["Informação em falta", "Ambiguidade", "Risco de âmbito", "Risco de prazo", "Risco orçamental", "Contradição"],
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
  risks: "issues",
  questions: "questions",
  noRisks: "✓",
  noQuestions: "—",
  listsPresent: "✓",
  evidence: "«»",
  categories: ["missing_information", "ambiguity", "scope_risk", "timeline_risk", "budget_risk", "contradiction"],
  complete: "✓",
  confirm: "?"
};
type StructuredResult = Pick<AcceptanceBuilderResult, "lists" | "missingFields" | "comparison" | "analysisLanguage" | "issues" | "questions">;

export function composeDocument(result: StructuredResult): AcceptanceBuilderResult["document"] {
  const words = WORDS[result.analysisLanguage.split("-")[0].toLowerCase()] ?? NEUTRAL;
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
  const gapText = gaps || (result.comparison ? words.complete : words.listsPresent);
  if (!result.comparison) summary = gapText;
  if (result.issues && result.questions) {
    const risks = result.issues.filter((issue) => issue.category !== "missing_information");
    const lines = risks.map((issue) => {
      const label = words.categories[ISSUE_CATEGORIES.indexOf(issue.category)];
      const evidence = issue.evidence ? `\n  ${words.evidence}: ${issue.evidence}` : "";
      return `- ${label}: ${issue.description}${evidence}`;
    });
    const questions = result.questions.map((item, index) => `${index + 1}. ${item.question}`);
    sections.push({ title: words.risks, content: lines.join("\n") || words.noRisks });
    sections.push({ title: words.questions, content: questions.join("\n") || words.noQuestions });
    if (risks.length) summary = `${words.risks}: ${risks.length}`;
    else if (questions.length) summary = `${words.questions}: ${questions.length}`;
  }
  sections.push({ title: words.gaps, content: gapText });
  return { summary, sections };
}

export function composeCopyText(result: StructuredResult): string {
  return composeDocument(result).sections.map(({ title, content }) => `${title}\n${content}`).join("\n\n");
}
