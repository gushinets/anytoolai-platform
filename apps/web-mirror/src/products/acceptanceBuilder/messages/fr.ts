import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const fr: Shape<typeof en> = {
  title: "Acceptance Builder",
  description: "Transformez un brief client en critères d’acceptation, ou vérifiez un livrable par rapport au brief.",
  quotaRemaining: "{remaining} sur {limit, plural, one {# exécution} other {# exécutions}} restante(s).",
  modes: {
    legend: "Mode",
    draft: "Rédiger les critères",
    check: "Vérifier le livrable",
  },
  fields: {
    briefText: "Brief du client",
    briefTextPlaceholder: "Collez le brief, la demande ou l’offre du client.",
    briefTextHelp: "Collez le brief tel quel.",
    deliverableText: "Travail terminé",
    deliverableTextPlaceholder: "Collez le texte du travail terminé.",
    deliverableTextHelp: "Collez le texte que vous comptez livrer.",
  },
  draft: {
    submit: "Rédiger les critères",
    running: "Rédaction des critères d’acceptation…",
    runFailed: "Une erreur est survenue lors de la rédaction des critères. Veuillez réessayer.",
    resultTitle: "Critères d’acceptation",
    placeholder: "Vos critères d’acceptation apparaîtront ici après leur rédaction.",
    regenerate: "Rédiger à nouveau",
  },
  check: {
    submit: "Vérifier le livrable",
    running: "Vérification de votre livrable…",
    runFailed: "Une erreur est survenue lors de la vérification. Veuillez réessayer.",
    resultTitle: "Vérification du livrable",
    placeholder: "Votre vérification apparaîtra ici après son exécution.",
    regenerate: "Vérifier à nouveau",
  },
  result: {
    verdictScope: "Le verdict repose sur quatre critères de revue généraux, et non sur chacun des critères listés ci-dessous.",
    recap: "Récapitulatif rédigé (affichage seul, non copié)",
  },
};
