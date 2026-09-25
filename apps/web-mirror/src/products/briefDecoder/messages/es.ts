import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const es: Shape<typeof en> = {
  title: "Brief Decoder",
  description: "Convierta el brief de un cliente en detalles estructurados, riesgos, preguntas por hacer y un resumen que puede copiar.",
  quotaRemaining: "Quedan {remaining} de {limit, plural, one {# análisis} many {# de análisis} other {# análisis}}.",
  fields: {
    briefText: "Brief del cliente",
    briefTextPlaceholder: "Pegue el brief, la solicitud o la oferta del cliente.",
    briefTextHelp: "Pegue el brief tal cual. Un brief más largo genera preguntas más precisas.",
  },
  decode: {
    submit: "Analizar brief",
    running: "Analizando su brief…",
    runFailed: "Algo salió mal al analizar su brief. Inténtelo de nuevo.",
    startAnother: "Analizar otro brief",
  },
  result: {
    brief: "Brief",
    notProvided: "No indicado",
    issues: "Problemas",
    noIssues: "No se encontraron problemas.",
    evidence: "Evidencia: {text}",
    questions: "{count, plural, one {# pregunta de aclaración} many {# de preguntas de aclaración} other {# preguntas de aclaración}}",
    noQuestions: "No se generaron preguntas de aclaración.",
    rationale: "Por qué preguntar: {text}",
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
