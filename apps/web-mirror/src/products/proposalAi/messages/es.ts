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
    freelancerPositioning: "Su experiencia y puntos fuertes",
    freelancerPositioningPlaceholder: "Describa la experiencia y los puntos fuertes que lo convierten en la persona adecuada.",
    freelancerPositioningHelp: "La propuesta se basa solo en lo que escriba aquí. Indique hechos verificables: herramientas, casos, resultados.",
    toneLegend: "Estilo de la propuesta",
    required: "obligatorio",
    languageLabel: "Idioma de la propuesta",
    languageHelp: "No es el idioma de la interfaz. De forma predeterminada, la propuesta se redacta en el idioma de la tarea.",
    languageAuto: "Como la tarea",
  },
  toneOptions: {
    warm: "Cercano y cordial",
    neutral: "Claro y profesional",
    firm: "Seguro y directo",
  },
  fieldNames: {
    taskText: "Descripción de la tarea",
    freelancerPositioning: "Su experiencia y puntos fuertes",
  },
  result: {
    gapsTitle: "Lo que su experiencia no cubre",
    gapsHint: "La propuesta no lo afirma. Complételo usted o no lo mencione.",
  },
  generate: {
    submit: "Generar propuesta",
    running: "Generando su propuesta…",
    runFailed: "Algo salió mal al generar su propuesta. Inténtelo de nuevo.",
    resultTitle: "Propuesta",
    placeholder: "Su propuesta aparecerá aquí después de generarla.",
    regenerate: "Regenerar propuesta",
  },
};
