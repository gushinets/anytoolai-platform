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
    freelancerPositioning: "Votre expérience et vos points forts",
    freelancerPositioningPlaceholder: "Décrivez l’expérience et les points forts qui font de vous le bon profil.",
    freelancerPositioningHelp: "La proposition repose uniquement sur ce que vous écrivez ici. Indiquez des faits vérifiables : outils, projets, résultats.",
    toneLegend: "Style de la proposition",
    required: "obligatoire",
    languageLabel: "Langue de la proposition",
    languageHelp: "Ce n’est pas la langue de l’interface. Par défaut, la proposition est rédigée dans la langue de la mission.",
    languageAuto: "Comme la mission",
  },
  toneOptions: {
    warm: "Chaleureux et personnel",
    neutral: "Clair et professionnel",
    firm: "Assuré et direct",
  },
  fieldNames: {
    taskText: "La description de la mission",
    freelancerPositioning: "Votre expérience et vos points forts",
  },
  result: {
    gapsTitle: "Ce que votre expérience ne couvre pas",
    gapsHint: "La proposition ne l’affirme pas. Complétez-le vous-même ou passez-le sous silence.",
  },
  generate: {
    submit: "Générer la proposition",
    running: "Génération de votre proposition…",
    runFailed: "Une erreur s’est produite lors de la génération de votre proposition. Veuillez réessayer.",
    resultTitle: "Proposition",
    placeholder: "Votre proposition apparaîtra ici après sa génération.",
    regenerate: "Régénérer la proposition",
  },
};
