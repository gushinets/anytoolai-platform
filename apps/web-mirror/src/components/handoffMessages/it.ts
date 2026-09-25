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
};
