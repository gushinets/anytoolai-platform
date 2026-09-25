import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const de: Shape<typeof en> = {
  title: "Übergabe prüfen",
  loading: "Übergabe wird geladen…",
  notFound: "Dieser Übergabe-Link ist ungültig.",
  loadFailed: "Beim Laden dieser Übergabe ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut.",
  retry: "Erneut versuchen",
  actionFailed: "Die Aktion konnte nicht abgeschlossen werden. Bitte versuchen Sie es erneut.",
  fields: {
    from: "Von",
    to: "An",
    expires: "Läuft ab",
    status: "Status",
  },
  accept: "Annehmen",
  decline: "Ablehnen",
  accepting: "Wird angenommen…",
  declining: "Wird abgelehnt…",
  status: {
    waiting: "Wartet auf Ihre Entscheidung",
    accepted: "Angenommen",
    declined: "Abgelehnt",
    expired: "Abgelaufen",
    failed: "Fehlgeschlagen",
  },
};
