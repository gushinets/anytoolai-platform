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
    freelancerPositioning: "Ihre Positionierung",
    freelancerPositioningPlaceholder: "Beschreiben Sie die Erfahrung und Stärken, die Sie für diese Aufgabe qualifizieren.",
    freelancerPositioningHelp: "Verwenden Sie nur Aussagen, hinter denen Sie stehen können — das Angebot erfindet keine Erfahrung.",
    toneLegend: "Angebotsstil",
  },
  toneOptions: {
    warm: "Warm & persönlich",
    neutral: "Klar & professionell",
    firm: "Selbstbewusst & direkt",
  },
  fieldNames: {
    taskText: "Die Aufgabenbeschreibung",
    freelancerPositioning: "Ihre Positionierung",
  },
  generate: {
    submit: "Angebot erstellen",
    running: "Ihr Angebot wird erstellt…",
    runFailed: "Beim Erstellen Ihres Angebots ist etwas schiefgelaufen. Bitte versuchen Sie es erneut.",
    startAnother: "Weiteres Angebot erstellen",
  },
};
