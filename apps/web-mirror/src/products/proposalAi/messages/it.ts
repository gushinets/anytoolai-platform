// Italian ProposalAI messages (ICU); typographic ’ only.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const it: Shape<typeof en> = {
  title: "ProposalAI",
  description: "Trasformi il brief di un cliente e i suoi punti di forza in una proposta pronta per l’invio.",
  quotaRemaining: "Ne restano {remaining} su {limit, plural, one {# proposta} many {# di proposte} other {# proposte}}.",
  fields: {
    taskText: "Descriva l’incarico",
    taskTextPlaceholder: "Incolli l’incarico, il brief o l’annuncio di lavoro del cliente.",
    taskTextHelp: "Includa l’obiettivo, i risultati attesi, i vincoli e la tempistica, se disponibili.",
    freelancerPositioning: "La sua esperienza e i suoi punti di forza",
    freelancerPositioningPlaceholder: "Descriva l’esperienza e i punti di forza che fanno di lei la persona giusta per l’incarico.",
    freelancerPositioningHelp: "La proposta si basa solo su ciò che scrive qui. Indichi fatti verificabili: strumenti, casi, risultati.",
    toneLegend: "Stile della proposta",
    required: "obbligatorio",
    languageLabel: "Lingua della proposta",
    languageHelp: "Non è la lingua dell’interfaccia. Per impostazione predefinita la proposta è scritta nella lingua dell’incarico.",
    languageAuto: "Come l’incarico",
  },
  toneOptions: {
    warm: "Caloroso e cordiale",
    neutral: "Chiaro e professionale",
    firm: "Sicuro e diretto",
  },
  fieldNames: {
    taskText: "Descrizione dell’incarico",
    freelancerPositioning: "La sua esperienza e i suoi punti di forza",
  },
  result: {
    gapsTitle: "Ciò che la sua esperienza non copre",
    gapsHint: "La proposta non lo afferma. Lo integri lei o lo ometta.",
  },
  generate: {
    submit: "Generi la proposta",
    running: "Generazione della proposta in corso…",
    runFailed: "Si è verificato un problema durante la generazione della proposta. Riprovare.",
    resultTitle: "Proposta",
    placeholder: "La proposta apparirà qui dopo la generazione.",
    regenerate: "Rigeneri la proposta",
  },
};
