import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const fr: Shape<typeof en> = {
  title: "Brief Decoder",
  description: "Transformez un brief client en détails structurés, risques, questions à poser et résumé à copier.",
  quotaRemaining: "{remaining} sur {limit, plural, one {# analyse} many {# d’analyses} other {# analyses}} restantes.",
  fields: {
    briefText: "Brief du client",
    briefTextPlaceholder: "Collez le brief, la demande ou l’annonce du client.",
    briefTextHelp: "Collez le brief tel quel. Un brief plus long donne des questions plus précises.",
  },
  decode: {
    submit: "Décoder le brief",
    running: "Décodage de votre brief…",
    runFailed: "Une erreur s’est produite lors du décodage de votre brief. Veuillez réessayer.",
    startAnother: "Décoder un autre brief",
  },
  result: {
    brief: "Brief",
    notProvided: "Non indiqué",
    issues: "Problèmes",
    noIssues: "Aucun problème détecté.",
    evidence: "Preuve : {text}",
    questions: "{count, plural, one {# question de clarification} many {# de questions de clarification} other {# questions de clarification}}",
    noQuestions: "Aucune question de clarification n’a été générée.",
    rationale: "Pourquoi la poser : {text}",
    document: "Document de synthèse",
  },
  briefFields: {
    project_goal: "Objectif du projet",
    deliverables: "Livrables",
    deadline: "Échéance",
    budget: "Budget",
    target_audience: "Public cible",
    constraints: "Contraintes",
  },
  severity: {
    low: "Gravité faible",
    medium: "Gravité moyenne",
    high: "Gravité élevée",
  },
  priority: {
    low: "Priorité basse",
    medium: "Priorité moyenne",
    high: "Priorité haute",
  },
  categories: {
    missing_information: "Information manquante",
    ambiguity: "Ambiguïté",
    scope_risk: "Risque de périmètre",
    timeline_risk: "Risque de délai",
    budget_risk: "Risque budgétaire",
    contradiction: "Contradiction",
  },
};
