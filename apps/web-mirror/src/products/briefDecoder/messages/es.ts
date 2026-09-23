import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const es: Shape<typeof en> = {
  title: "Brief Decoder",
  description: "Convierte el brief de un cliente en detalles estructurados, riesgos, preguntas por hacer y un resumen que puedes copiar.",
  quotaRemaining: "Quedan {remaining} de {limit, plural, one {# análisis} many {# de análisis} other {# análisis}}.",
  fields: {
    briefText: "Brief del cliente",
    briefTextPlaceholder: "Pega el brief, la solicitud o la oferta del cliente.",
    briefTextHelp: "Pega el brief tal cual. Un brief más largo genera preguntas más precisas.",
  },
  fieldNames: {
    briefText: "Brief del cliente",
  },
  decode: {
    submit: "Analizar brief",
    running: "Analizando tu brief…",
    runFailed: "Algo salió mal al analizar tu brief. Inténtalo de nuevo.",
    startAnother: "Analizar otro brief",
  },
  result: {
    brief: "Brief",
    notProvided: "No indicado",
    issues: "Problemas",
    noIssues: "No se encontraron problemas.",
    evidence: "Evidencia",
    questions: "{count, plural, one {# pregunta de aclaración} many {# de preguntas de aclaración} other {# preguntas de aclaración}}",
    noQuestions: "No se generaron preguntas de aclaración.",
    rationale: "Por qué preguntar",
    document: "Documento resumen",
  },
  briefFields: {
    project_goal: "Objetivo del proyecto",
    deliverables: "Entregables",
    deadline: "Fecha límite",
    budget: "Presupuesto",
    target_audience: "Público objetivo",
    constraints: "Restricciones",
  },
  severity: {
    low: "Gravedad baja",
    medium: "Gravedad media",
    high: "Gravedad alta",
  },
  priority: {
    low: "Prioridad baja",
    medium: "Prioridad media",
    high: "Prioridad alta",
  },
  categories: {
    missing_information: "Información faltante",
    ambiguity: "Ambigüedad",
    scope_risk: "Riesgo de alcance",
    timeline_risk: "Riesgo de plazo",
    budget_risk: "Riesgo de presupuesto",
    contradiction: "Contradicción",
  },
};
