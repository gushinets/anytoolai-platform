import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const pt: Shape<typeof en> = {
  title: "Brief Decoder",
  description: "Transforme o briefing de um cliente em detalhes estruturados, riscos, perguntas a fazer e um resumo para copiar.",
  quotaRemaining: "{remaining} de {limit, plural, one {# análise} many {# de análises} other {# análises}} restantes.",
  fields: {
    briefText: "Briefing do cliente",
    briefTextPlaceholder: "Cole o briefing, o pedido ou o anúncio do cliente.",
    briefTextHelp: "Cole o briefing como está. Um briefing mais longo gera perguntas mais precisas.",
  },
  fieldNames: {
    briefText: "Briefing do cliente",
  },
  decode: {
    submit: "Decodificar briefing",
    running: "Decodificando o seu briefing…",
    runFailed: "Algo correu mal ao decodificar o seu briefing. Tente novamente.",
    startAnother: "Decodificar outro briefing",
  },
  result: {
    brief: "Briefing",
    notProvided: "Não informado",
    issues: "Problemas",
    noIssues: "Nenhum problema encontrado.",
    evidence: "Evidência",
    questions: "{count, plural, one {# pergunta de esclarecimento} many {# de perguntas de esclarecimento} other {# perguntas de esclarecimento}}",
    noQuestions: "Nenhuma pergunta de esclarecimento foi gerada.",
    rationale: "Por que perguntar",
    document: "Documento-resumo",
  },
  briefFields: {
    project_goal: "Objetivo do projeto",
    deliverables: "Entregas",
    deadline: "Prazo",
    budget: "Orçamento",
    target_audience: "Público-alvo",
    constraints: "Restrições",
  },
  severity: {
    low: "Gravidade baixa",
    medium: "Gravidade média",
    high: "Gravidade alta",
  },
  priority: {
    low: "Prioridade baixa",
    medium: "Prioridade média",
    high: "Prioridade alta",
  },
  categories: {
    missing_information: "Informação em falta",
    ambiguity: "Ambiguidade",
    scope_risk: "Risco de escopo",
    timeline_risk: "Risco de prazo",
    budget_risk: "Risco de orçamento",
    contradiction: "Contradição",
  },
};
