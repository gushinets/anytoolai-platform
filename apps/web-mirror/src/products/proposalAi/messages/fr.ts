// French ProposalAI messages; typed against the English source of truth.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const fr: Shape<typeof en> = {
  title: "ProposalAI",
  quotaRemaining: "Il vous en reste {remaining} sur {limit, plural, one {# proposition} many {# de propositions} other {# propositions}}.",
  fields: {
    taskText: "Décrivez la mission",
    freelancerPositioning: "Votre positionnement",
    tone: "Ton (facultatif)",
    tonePlaceholder: "Par défaut",
    language: "Langue (facultatif)",
  },
  fieldNames: {
    taskText: "La description de la mission",
    freelancerPositioning: "Votre positionnement",
  },
  validation: { languageFormat: 'La langue doit ressembler à "en" ou "en-US".' },
  generate: {
    submit: "Générer la proposition",
    running: "Génération de votre proposition…",
    runFailed: "Une erreur s’est produite lors de la génération de votre proposition. Veuillez réessayer.",
  },
};
