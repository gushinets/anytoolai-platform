import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const it: Shape<typeof en> = {
  title: "Verifica il trasferimento",
  loading: "Caricamento del trasferimento…",
  notFound: "Questo link di trasferimento non è valido.",
  loadFailed: "Si è verificato un problema durante il caricamento di questo trasferimento. Riprovi.",
  retry: "Riprova",
  actionFailed: "Non è stato possibile completare l’azione. Riprovi.",
  fields: {
    from: "Da",
    to: "A",
    expires: "Scade il",
    status: "Stato",
  },
  // Shown on a spent (accepted/consumed) token that still names the queued target session.
  openResult: "Apri il risultato",
  accept: "Accetta",
  decline: "Rifiuta",
  accepting: "Accettazione…",
  declining: "Rifiuto…",
  status: {
    waiting: "In attesa della sua decisione",
    accepted: "Accettato",
    declined: "Rifiutato",
    expired: "Scaduto",
    failed: "Non riuscito",
  },
  // Labels for the backend's known preview keys (`handoffs.yaml` `preview_mapping`); any other key is shown as sent.
  previewFields: {
    summary: "Riepilogo",
    missing_fields: "Informazioni mancanti",
  },
};
