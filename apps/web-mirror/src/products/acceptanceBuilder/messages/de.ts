import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const de: Shape<typeof en> = {
  title: "Acceptance Builder",
  description: "Machen Sie aus einem Kunden-Briefing Abnahmekriterien oder prüfen Sie fertige Arbeit gegen das Briefing.",
  quotaRemaining: "{remaining} von {limit, plural, one {# Durchlauf} other {# Durchläufen}} übrig.",
  modes: {
    legend: "Modus",
    draft: "Kriterien entwerfen",
    check: "Ergebnis prüfen",
  },
  fields: {
    briefText: "Kunden-Briefing",
    briefTextPlaceholder: "Fügen Sie das Briefing, die Anfrage oder die Ausschreibung des Kunden ein.",
    briefTextHelp: "Fügen Sie das Briefing unverändert ein.",
    deliverableText: "Fertige Arbeit",
    deliverableTextPlaceholder: "Fügen Sie den Text der fertigen Arbeit ein.",
    deliverableTextHelp: "Fügen Sie den Text ein, den Sie übergeben wollen.",
  },
  draft: {
    submit: "Kriterien entwerfen",
    running: "Abnahmekriterien werden entworfen…",
    runFailed: "Beim Entwerfen der Kriterien ist etwas schiefgelaufen. Bitte versuchen Sie es erneut.",
    resultTitle: "Abnahmekriterien",
    placeholder: "Ihre Abnahmekriterien erscheinen hier, sobald Sie sie entworfen haben.",
    regenerate: "Kriterien erneut entwerfen",
  },
  check: {
    submit: "Ergebnis prüfen",
    running: "Ergebnis wird geprüft…",
    runFailed: "Bei der Prüfung ist etwas schiefgelaufen. Bitte versuchen Sie es erneut.",
    resultTitle: "Ergebnisprüfung",
    placeholder: "Ihre Prüfung erscheint hier, sobald Sie sie ausgeführt haben.",
    regenerate: "Erneut prüfen",
  },
  result: {
    verdictScope: "Das Urteil beruht auf vier allgemeinen Prüfkriterien, nicht Punkt für Punkt auf den unten aufgeführten Kriterien.",
    recap: "Erzählende Zusammenfassung (nur Anzeige, nicht kopiert)",
  },
};
