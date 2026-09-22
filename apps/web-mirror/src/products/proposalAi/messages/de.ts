// German ProposalAI messages (Sie-Form).
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const de: Shape<typeof en> = {
  title: "ProposalAI",
  quotaRemaining: "{remaining} von {limit, plural, one {# Angebot} other {# Angeboten}} verbleibend.",
  fields: {
    taskText: "Beschreiben Sie die Aufgabe",
    freelancerPositioning: "Ihre Positionierung",
    tone: "Tonalität (optional)",
    tonePlaceholder: "Standard",
    language: "Sprache (optional)",
  },
  fieldNames: {
    taskText: "Die Aufgabenbeschreibung",
    freelancerPositioning: "Ihre Positionierung",
    language: "Sprache",
  },
  validation: { languageFormat: 'Die Sprache muss wie "en" oder "en-US" aussehen.' },
  generate: {
    submit: "Angebot erstellen",
    running: "Ihr Angebot wird erstellt…",
    runFailed: "Beim Erstellen Ihres Angebots ist etwas schiefgelaufen. Bitte versuchen Sie es erneut.",
  },
};
