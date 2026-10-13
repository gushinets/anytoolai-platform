// German ProposalAI messages (Sie-Form).
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const de: Shape<typeof en> = {
  title: "ProposalAI",
  description:
    "Verwandeln Sie ein Kundenbriefing und Ihre relevanten Stärken in ein versandfertiges Angebot.",
  quotaRemaining: "{remaining} von {limit, plural, one {# Angebot} other {# Angeboten}} verbleibend.",
  fields: {
    taskText: "Beschreiben Sie die Aufgabe",
    taskTextPlaceholder: "Fügen Sie die Aufgabe, das Briefing oder die Stellenausschreibung des Kunden ein.",
    taskTextHelp: "Geben Sie nach Möglichkeit Ziel, Leistungen, Rahmenbedingungen und Zeitplan an.",
    freelancerPositioning: "Ihre Erfahrung und Stärken",
    freelancerPositioningPlaceholder: "Beschreiben Sie die Erfahrung und Stärken, die Sie für diese Aufgabe qualifizieren.",
    freelancerPositioningHelp: "Das Angebot basiert nur auf dem, was Sie hier schreiben. Nennen Sie überprüfbare Fakten: Werkzeuge, Projekte, Ergebnisse.",
    toneLegend: "Angebotsstil",
    required: "erforderlich",
    languageLabel: "Sprache des Angebots",
    languageHelp: "Nicht die Sprache der Oberfläche. Standardmäßig wird das Angebot in der Sprache der Aufgabe verfasst.",
    languageAuto: "Wie in der Aufgabe",
  },
  toneOptions: {
    warm: "Warm & persönlich",
    neutral: "Klar & professionell",
    firm: "Selbstbewusst & direkt",
  },
  fieldNames: {
    taskText: "Die Aufgabenbeschreibung",
    freelancerPositioning: "Ihre Erfahrung und Stärken",
  },
  result: {
    gapsTitle: "Nicht durch Ihre Erfahrung abgedeckt",
    gapsHint: "Das Angebot behauptet dies nicht. Ergänzen Sie es selbst oder lassen Sie es weg.",
  },
  generate: {
    submit: "Angebot erstellen",
    running: "Ihr Angebot wird erstellt…",
    runFailed: "Beim Erstellen Ihres Angebots ist etwas schiefgelaufen. Bitte versuchen Sie es erneut.",
    resultTitle: "Angebot",
    placeholder: "Ihr Angebot erscheint nach dem Erstellen hier.",
    regenerate: "Angebot erneut erstellen",
  },
};
