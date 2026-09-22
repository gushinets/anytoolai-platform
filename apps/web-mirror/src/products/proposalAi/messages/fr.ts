// French ProposalAI messages; typed against the English source of truth.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const fr: Shape<typeof en> = {
  title: "ProposalAI",
  description: "Transformez le brief d’un client et vos points forts en une proposition prête à être envoyée.",
  quotaRemaining: "Il vous en reste {remaining} sur {limit, plural, one {# proposition} many {# de propositions} other {# propositions}}.",
  fields: {
    taskText: "Décrivez la mission",
    taskTextPlaceholder: "Collez la mission, le brief ou l’offre du client.",
    taskTextHelp: "Indiquez l’objectif, les livrables, les contraintes et le calendrier si possible.",
    freelancerPositioning: "Votre positionnement",
    freelancerPositioningPlaceholder: "Décrivez l’expérience et les points forts qui font de vous le bon profil.",
    freelancerPositioningHelp: "N’avancez que ce que vous pouvez assumer : la proposition n’inventera pas d’expérience.",
    toneLegend: "Style de la proposition",
  },
  toneOptions: {
    warm: "Chaleureux et personnel",
    neutral: "Clair et professionnel",
    firm: "Assuré et direct",
  },
  fieldNames: {
    taskText: "La description de la mission",
    freelancerPositioning: "Votre positionnement",
  },
  generate: {
    submit: "Générer la proposition",
    running: "Génération de votre proposition…",
    runFailed: "Une erreur s’est produite lors de la génération de votre proposition. Veuillez réessayer.",
    startAnother: "Créer une autre proposition",
  },
};
