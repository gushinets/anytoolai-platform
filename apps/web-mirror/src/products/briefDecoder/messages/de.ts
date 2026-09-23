import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const de: Shape<typeof en> = {
  title: "Brief Decoder",
  description: "Verwandeln Sie ein Kunden-Briefing in strukturierte Angaben, Risiken, Rückfragen und eine kopierbare Zusammenfassung.",
  quotaRemaining: "Noch {remaining} von {limit, plural, one {# Analyse} other {# Analysen}} verfügbar.",
  fields: {
    briefText: "Kunden-Briefing",
    briefTextPlaceholder: "Fügen Sie das Briefing, die Anfrage oder die Stellenanzeige des Kunden ein.",
    briefTextHelp: "Fügen Sie das Briefing unverändert ein. Ein ausführlicheres Briefing ergibt genauere Fragen.",
  },
  fieldNames: {
    briefText: "Kunden-Briefing",
  },
  decode: {
    submit: "Briefing analysieren",
    running: "Ihr Briefing wird analysiert…",
    runFailed: "Beim Analysieren Ihres Briefings ist etwas schiefgelaufen. Bitte versuchen Sie es erneut.",
    startAnother: "Weiteres Briefing analysieren",
  },
  result: {
    brief: "Briefing",
    notProvided: "Nicht angegeben",
    issues: "Probleme",
    noIssues: "Keine Probleme gefunden.",
    evidence: "Beleg",
    questions: "{count, plural, one {# Rückfrage} other {# Rückfragen}}",
    noQuestions: "Es wurden keine Rückfragen erzeugt.",
    rationale: "Warum fragen",
    document: "Zusammenfassung",
  },
  briefFields: {
    project_goal: "Projektziel",
    deliverables: "Liefergegenstände",
    deadline: "Frist",
    budget: "Budget",
    target_audience: "Zielgruppe",
    constraints: "Einschränkungen",
  },
  severity: {
    low: "Geringe Schwere",
    medium: "Mittlere Schwere",
    high: "Hohe Schwere",
  },
  priority: {
    low: "Niedrige Priorität",
    medium: "Mittlere Priorität",
    high: "Hohe Priorität",
  },
  categories: {
    missing_information: "Fehlende Informationen",
    ambiguity: "Mehrdeutigkeit",
    scope_risk: "Umfangsrisiko",
    timeline_risk: "Terminrisiko",
    budget_risk: "Budgetrisiko",
    contradiction: "Widerspruch",
  },
};
