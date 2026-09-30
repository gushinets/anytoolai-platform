import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const fr: Shape<typeof en> = {
  title: "AnytoolAI",
  lead: "De petits outils pour freelances. Décrivez la mission, obtenez un texte prêt à envoyer au client.",
  open: "Ouvrir",
  cards: {
    proposal_ai: {
      blurb: "Transformez le brief d'un client et vos atouts en une proposition prête à envoyer.",
      sample: "Bonjour Dana, je serais ravi de vous aider à refondre votre page d'atterrissage. Deux cycles de retouches, livraison en trois semaines. Fixons un court appel pour confirmer le périmètre.",
    },
    client_update_writer: {
      blurb: "Rédigez un point d'avancement, une réponse à un message client ou une demande d'acompte, sur le ton de votre choix.",
      sample: "Point rapide : la refonte de la page d'accueil est terminée et prête à être relue d'ici vendredi. Aucun blocage pour l'instant.",
      tags: {
        update: "Mise à jour",
        replyDraft: "Brouillon de réponse",
        prepaidRequest: "Demande d'acompte",
      },
    },
    brief_decoder: {
      blurb: "Transformez un brief client en détails structurés, risques et questions à poser avant de commencer.",
      sample: "Manquant : échéance et budget. À demander au client : quelle est la date de lancement exacte, et qui valide le design ?",
    },
    acceptance_builder: {
      blurb: "Transformez un brief en critères d’acceptation, ou vérifiez un livrable par rapport au brief.",
      sample: "Critères d’acceptation : la page d’accueil se charge en moins de deux secondes ; le client valide deux tours de design.",
      tags: {
        draft: "Rédiger les critères",
        check: "Vérifier le livrable",
      },
    },
  },
};
