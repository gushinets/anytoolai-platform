import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const it: Shape<typeof en> = {
  title: "Brief Decoder",
  description: "Trasforma il brief di un cliente in dettagli strutturati, rischi, domande da porre e un riepilogo da copiare.",
  quotaRemaining: "{remaining} su {limit, plural, one {# analisi} many {# di analisi} other {# analisi}} rimaste.",
  fields: {
    briefText: "Brief del cliente",
    briefTextPlaceholder: "Incolla il brief, la richiesta o l’annuncio del cliente.",
    briefTextHelp: "Incolla il brief così com’è. Un brief più lungo produce domande più precise.",
  },
  fieldNames: {
    briefText: "Brief del cliente",
  },
  decode: {
    submit: "Decodifica il brief",
    running: "Decodifica del brief in corso…",
    runFailed: "Qualcosa è andato storto nella decodifica del brief. Riprova.",
    startAnother: "Decodifica un altro brief",
  },
  result: {
    brief: "Brief",
    notProvided: "Non indicato",
    issues: "Problemi",
    noIssues: "Nessun problema rilevato.",
    evidence: "Evidenza",
    questions: "{count, plural, one {# domanda di chiarimento} many {# di domande di chiarimento} other {# domande di chiarimento}}",
    noQuestions: "Non è stata generata alcuna domanda di chiarimento.",
    rationale: "Perché chiederlo",
    document: "Documento di riepilogo",
  },
  briefFields: {
    project_goal: "Obiettivo del progetto",
    deliverables: "Consegne",
    deadline: "Scadenza",
    budget: "Budget",
    target_audience: "Pubblico di riferimento",
    constraints: "Vincoli",
  },
  severity: {
    low: "Gravità bassa",
    medium: "Gravità media",
    high: "Gravità alta",
  },
  priority: {
    low: "Priorità bassa",
    medium: "Priorità media",
    high: "Priorità alta",
  },
  categories: {
    missing_information: "Informazioni mancanti",
    ambiguity: "Ambiguità",
    scope_risk: "Rischio di ambito",
    timeline_risk: "Rischio di tempistica",
    budget_risk: "Rischio di budget",
    contradiction: "Contraddizione",
  },
};
