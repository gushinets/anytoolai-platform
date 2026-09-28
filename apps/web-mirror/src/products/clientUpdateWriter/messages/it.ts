// Italian Client Update Writer messages (ICU); typographic ’ only.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";
import { it as tone } from "../../shared/toneMessages/it";

export const it: Shape<typeof en> = {
  title: "Client Update Writer",
  tone,
  quotaRemaining: "Ne restano {remaining} su {limit, plural, one {# esecuzione di Client Update Writer} many {# di esecuzioni di Client Update Writer} other {# esecuzioni di Client Update Writer}}.",
  modes: {
    legend: "Modalità",
    update: "Aggiornamento",
    reply_draft: "Bozza di risposta",
    prepaid_request: "Richiesta di pagamento anticipato",
  },
  fields: {
    progressNotes: "Note sull’avanzamento",
    clientMessage: "Messaggio del cliente",
    replyGoal: "Obiettivo della risposta",
    billingNotes: "Note di fatturazione",
    billingAmount: "Importo",
    billingDueDate: "Scadenza (facoltativa)",
    tone: "Tono",
    tonePlaceholder: "Selezionare un tono",
  },
  fieldNames: {
    progressNotes: "Note sull’avanzamento",
    clientMessage: "Messaggio del cliente",
    replyGoal: "Obiettivo della risposta",
    billingNotes: "Note di fatturazione",
    billingAmount: "Importo",
    billingDueDate: "Scadenza",
    tone: "Tono",
  },
  update: {
    submit: "Scrivere l’aggiornamento",
    running: "Scrittura dell’aggiornamento in corso…",
    runFailed: "Si è verificato un problema durante la scrittura dell’aggiornamento. Riprovare.",
    resultTitle: "Aggiornamento",
    placeholder: "L’aggiornamento apparirà qui dopo la scrittura.",
    regenerate: "Riscrivere l’aggiornamento",
  },
  reply_draft: {
    submit: "Scrivere la risposta",
    running: "Scrittura della risposta in corso…",
    runFailed: "Si è verificato un problema durante la scrittura della risposta. Riprovare.",
    resultTitle: "Bozza di risposta",
    placeholder: "La risposta apparirà qui dopo la scrittura.",
    regenerate: "Riscrivere la risposta",
  },
  prepaid_request: {
    submit: "Scrivere la richiesta",
    running: "Scrittura della richiesta in corso…",
    runFailed: "Si è verificato un problema durante la scrittura della richiesta. Riprovare.",
    resultTitle: "Richiesta di pagamento anticipato",
    placeholder: "La richiesta apparirà qui dopo la scrittura.",
    regenerate: "Riscrivere la richiesta",
  },
};
