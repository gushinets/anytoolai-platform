// French Client Update Writer messages; typed against the English source of truth.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const fr: Shape<typeof en> = {
  title: "Client Update Writer",
  quotaRemaining: "Il vous en reste {remaining} sur {limit, plural, one {# exécution de Client Update Writer} many {# d’exécutions de Client Update Writer} other {# exécutions de Client Update Writer}}.",
  modes: {
    legend: "Mode",
    update: "Point d’avancement",
    reply_draft: "Brouillon de réponse",
    prepaid_request: "Demande de paiement d’avance",
  },
  fields: {
    progressNotes: "Notes d’avancement",
    clientMessage: "Message du client",
    replyGoal: "Objectif de la réponse",
    billingNotes: "Notes de facturation",
    billingAmount: "Montant",
    billingDueDate: "Date d’échéance (facultatif)",
    tone: "Ton",
    tonePlaceholder: "Sélectionnez un ton",
  },
  fieldNames: {
    progressNotes: "Les notes d’avancement",
    clientMessage: "Le message du client",
    replyGoal: "L’objectif de la réponse",
    billingNotes: "Les notes de facturation",
    billingAmount: "Le montant",
    billingDueDate: "La date d’échéance",
    tone: "Le ton",
  },
  update: {
    submit: "Rédiger le point d’avancement",
    running: "Rédaction de votre point d’avancement…",
    runFailed: "Une erreur s’est produite lors de la rédaction de votre point d’avancement. Veuillez réessayer.",
  },
  reply_draft: {
    submit: "Rédiger la réponse",
    running: "Rédaction de votre réponse…",
    runFailed: "Une erreur s’est produite lors de la rédaction de votre réponse. Veuillez réessayer.",
  },
  prepaid_request: {
    submit: "Rédiger la demande",
    running: "Rédaction de votre demande…",
    runFailed: "Une erreur s’est produite lors de la rédaction de votre demande. Veuillez réessayer.",
  },
};
