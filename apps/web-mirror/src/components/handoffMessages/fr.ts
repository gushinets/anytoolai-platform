import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const fr: Shape<typeof en> = {
  title: "Vérifier le transfert",
  loading: "Chargement du transfert…",
  notFound: "Ce lien de transfert n’est pas valide.",
  loadFailed: "Un problème est survenu lors du chargement de ce transfert. Veuillez réessayer.",
  retry: "Réessayer",
  actionFailed: "Cette action n’a pas pu être effectuée. Veuillez réessayer.",
  fields: {
    from: "De",
    to: "À",
    expires: "Expire le",
    status: "Statut",
  },
  accept: "Accepter",
  decline: "Refuser",
  accepting: "Acceptation…",
  declining: "Refus…",
  status: {
    waiting: "En attente de votre décision",
    accepted: "Accepté",
    declined: "Refusé",
    expired: "Expiré",
    failed: "Échec",
  },
};
