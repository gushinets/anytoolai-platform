// French host messages; typed against the English source of truth.
import type { Shape } from "../messageTypes";
import type { en } from "./en";

export const fr: Shape<typeof en> = {
  language: { label: "Langue" },
  loading: "Chargement de {product}…",
  unavailable: "{product} est indisponible pour le moment. Veuillez recharger la page.",
  quotaExhausted: "Vous avez utilisé toutes vos exécutions de {product} pour le moment.",
  resultFetchFailed: "Votre résultat est prêt, mais nous n’avons pas pu le charger. Veuillez réessayer.",
  starting: "Démarrage…",
  generating: "Génération en cours…",
  identityUnavailable: "Nous n’avons pas pu vérifier votre identité. Veuillez recharger la page et réessayer.",
  retry: "Réessayer",
  errors: {
    startFailed: "Impossible de démarrer {product}. Veuillez réessayer.",
    timeout: "Cela prend plus de temps que prévu. Veuillez réessayer.",
    connectionLost: "Connexion perdue pendant l’attente de votre résultat. Veuillez réessayer.",
    tryAgain: "Veuillez réessayer.",
  },
  result: {
    copy: "Copier",
    copying: "Copie en cours…",
    copied: "Copié",
    copyFailed: "Impossible de copier dans le presse-papiers. Veuillez copier le texte ci-dessus manuellement.",
  },
  validation: {
    required: "{field} est obligatoire.",
    outerWhitespace: "{field} ne doit ni commencer ni se terminer par un espace.",
    maxLength: "{field} ne doit pas dépasser {maxLength, plural, one {# caractère} many {# de caractères} other {# caractères}}.",
  },
  tone: { neutral: "neutre", warm: "chaleureux", firm: "ferme" },
};
