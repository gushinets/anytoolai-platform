// Italian ProposalAI messages (ICU); typographic ’ only.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const it: Shape<typeof en> = {
  title: "ProposalAI",
  quotaRemaining: "Ne restano {remaining} su {limit, plural, one {# proposta} many {# di proposte} other {# proposte}}.",
  fields: {
    taskText: "Descrivere l’incarico",
    freelancerPositioning: "Il suo posizionamento",
    tone: "Tono (facoltativo)",
    tonePlaceholder: "Predefinito",
    language: "Lingua (facoltativa)",
  },
  fieldNames: {
    taskText: "Descrizione dell’incarico",
    freelancerPositioning: "Il suo posizionamento",
    language: "Lingua",
  },
  validation: { languageFormat: 'Il formato della lingua deve essere simile a "en" o "en-US".' },
  generate: {
    submit: "Genera proposta",
    running: "Generazione della proposta in corso…",
    runFailed: "Si è verificato un problema durante la generazione della proposta. Riprovare.",
  },
};
