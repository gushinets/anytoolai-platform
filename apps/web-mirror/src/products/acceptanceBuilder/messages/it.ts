import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const it: Shape<typeof en> = {
  title: "Acceptance Builder",
  description: "Trasformare il brief del cliente in criteri di accettazione, o verificare il lavoro finito rispetto al brief.",
  quotaRemaining: "{remaining} di {limit, plural, one {# esecuzione} other {# esecuzioni}} rimanenti.",
  modes: {
    legend: "Modalità",
    draft: "Redigi i criteri",
    check: "Verifica il lavoro",
  },
  fields: {
    briefText: "Brief del cliente",
    briefTextPlaceholder: "Incollare il brief, la richiesta o l’annuncio del cliente.",
    briefTextHelp: "Incollare il brief così com’è.",
    deliverableText: "Lavoro finito",
    deliverableTextPlaceholder: "Incollare il testo del lavoro finito.",
    deliverableTextHelp: "Incollare il testo da consegnare.",
  },
  draft: {
    submit: "Redigi i criteri",
    running: "Redazione dei criteri di accettazione…",
    runFailed: "Qualcosa è andato storto nella redazione dei criteri. Riprovare.",
    resultTitle: "Criteri di accettazione",
    placeholder: "I criteri di accettazione appariranno qui dopo la redazione.",
    regenerate: "Redigi di nuovo",
  },
  check: {
    submit: "Verifica il lavoro",
    running: "Verifica del lavoro in corso…",
    runFailed: "Qualcosa è andato storto nella verifica. Riprovare.",
    resultTitle: "Verifica del lavoro",
    placeholder: "La verifica apparirà qui dopo l’esecuzione.",
    regenerate: "Verifica di nuovo",
  },
  result: {
    verdictScope: "Il verdetto si basa su quattro criteri di revisione generali, non voce per voce sui criteri elencati sotto.",
    recap: "Riepilogo narrativo (solo visualizzazione, non copiato)",
  },
};
