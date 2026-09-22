// Spanish (neutral) ProposalAI messages; keys mirror en.ts.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const es: Shape<typeof en> = {
  title: "ProposalAI",
  description: "Convierta el briefing del cliente y sus puntos fuertes relevantes en una propuesta lista para enviar.",
  quotaRemaining: "Quedan {remaining} de {limit, plural, one {# propuesta} many {# de propuestas} other {# propuestas}}.",
  fields: {
    taskText: "Describa la tarea",
    taskTextPlaceholder: "Pegue la tarea, el briefing o la oferta de trabajo del cliente.",
    taskTextHelp: "Incluya el objetivo, los entregables, las restricciones y el plazo cuando estén disponibles.",
    freelancerPositioning: "Su posicionamiento",
    freelancerPositioningPlaceholder: "Describa la experiencia y los puntos fuertes que lo convierten en la persona adecuada.",
    freelancerPositioningHelp: "Use solo afirmaciones que pueda respaldar: la propuesta no inventará experiencia.",
    toneLegend: "Estilo de la propuesta",
  },
  toneOptions: {
    warm: "Cercano y cordial",
    neutral: "Claro y profesional",
    firm: "Seguro y directo",
  },
  fieldNames: {
    taskText: "Descripción de la tarea",
    freelancerPositioning: "Su posicionamiento",
  },
  generate: {
    submit: "Generar propuesta",
    running: "Generando su propuesta…",
    runFailed: "Algo salió mal al generar su propuesta. Inténtelo de nuevo.",
    startAnother: "Crear otra propuesta",
  },
};
