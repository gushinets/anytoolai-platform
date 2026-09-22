// Spanish (neutral) Client Update Writer messages; keys mirror en.ts.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";
import { es as tone } from "../../shared/toneMessages/es";

export const es: Shape<typeof en> = {
  title: "Client Update Writer",
  tone,
  quotaRemaining: "Quedan {remaining} de {limit, plural, one {# ejecución de Client Update Writer} many {# de ejecuciones de Client Update Writer} other {# ejecuciones de Client Update Writer}}.",
  modes: {
    legend: "Modo",
    update: "Actualización",
    reply_draft: "Borrador de respuesta",
    prepaid_request: "Solicitud de prepago",
  },
  fields: {
    progressNotes: "Notas de avance",
    clientMessage: "Mensaje del cliente",
    replyGoal: "Objetivo de la respuesta",
    billingNotes: "Notas de facturación",
    billingAmount: "Monto",
    billingDueDate: "Fecha de vencimiento (opcional)",
    tone: "Tono",
    tonePlaceholder: "Seleccione un tono",
  },
  fieldNames: {
    progressNotes: "Notas de avance",
    clientMessage: "Mensaje del cliente",
    replyGoal: "Objetivo de la respuesta",
    billingNotes: "Notas de facturación",
    billingAmount: "Monto",
    billingDueDate: "Fecha de vencimiento",
    tone: "Tono",
  },
  update: {
    submit: "Redactar actualización",
    running: "Redactando su actualización…",
    runFailed: "Algo salió mal al redactar su actualización. Inténtelo de nuevo.",
  },
  reply_draft: {
    submit: "Redactar respuesta",
    running: "Redactando su respuesta…",
    runFailed: "Algo salió mal al redactar su respuesta. Inténtelo de nuevo.",
  },
  prepaid_request: {
    submit: "Redactar solicitud",
    running: "Redactando su solicitud…",
    runFailed: "Algo salió mal al redactar su solicitud. Inténtelo de nuevo.",
  },
};
