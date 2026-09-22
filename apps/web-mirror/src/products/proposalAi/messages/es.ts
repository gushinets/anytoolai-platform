// Spanish (neutral) ProposalAI messages; keys mirror en.ts.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const es: Shape<typeof en> = {
  title: "ProposalAI",
  quotaRemaining: "Quedan {remaining} de {limit, plural, one {# propuesta} many {# de propuestas} other {# propuestas}}.",
  fields: {
    taskText: "Describa la tarea",
    freelancerPositioning: "Su posicionamiento",
    tone: "Tono (opcional)",
    tonePlaceholder: "Predeterminado",
    language: "Idioma (opcional)",
  },
  fieldNames: {
    taskText: "Descripción de la tarea",
    freelancerPositioning: "Su posicionamiento",
    language: "Idioma",
  },
  validation: { languageFormat: 'El idioma debe tener un formato como "en" o "en-US".' },
  generate: {
    submit: "Generar propuesta",
    running: "Generando su propuesta…",
    runFailed: "Algo salió mal al generar su propuesta. Inténtelo de nuevo.",
  },
};
