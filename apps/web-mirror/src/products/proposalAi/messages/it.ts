// Italian ProposalAI messages (ICU); typographic ’ only.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const it: Shape<typeof en> = {
  title: "ProposalAI",
  description: "Trasformi il brief di un cliente e i suoi punti di forza in una proposta pronta per l’invio.",
  quotaRemaining: "Ne restano {remaining} su {limit, plural, one {# proposta} many {# di proposte} other {# proposte}}.",
  fields: {
    taskText: "Descrivere l’incarico",
    taskTextPlaceholder: "Incolli l’incarico, il brief o l’annuncio di lavoro del cliente.",
    taskTextHelp: "Includa l’obiettivo, i risultati attesi, i vincoli e la tempistica, se disponibili.",
    freelancerPositioning: "Il suo posizionamento",
    freelancerPositioningPlaceholder: "Descriva l’esperienza e i punti di forza che fanno di lei la persona giusta per l’incarico.",
    freelancerPositioningHelp: "Indichi solo affermazioni verificabili: la proposta non inventerà esperienza.",
    toneLegend: "Stile della proposta",
  },
  toneOptions: {
    warm: "Caloroso e cordiale",
    neutral: "Chiaro e professionale",
    firm: "Sicuro e diretto",
  },
  fieldNames: {
    taskText: "Descrizione dell’incarico",
    freelancerPositioning: "Il suo posizionamento",
  },
  generate: {
    submit: "Generare la proposta",
    running: "Generazione della proposta in corso…",
    runFailed: "Si è verificato un problema durante la generazione della proposta. Riprovare.",
    startAnother: "Creare un’altra proposta",
  },
};
