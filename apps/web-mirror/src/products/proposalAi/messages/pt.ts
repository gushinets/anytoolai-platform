// Portuguese (generic) ProposalAI messages.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const pt: Shape<typeof en> = {
  title: "ProposalAI",
  description: "Transforme um briefing do cliente e seus pontos fortes relevantes em uma proposta pronta para enviar.",
  quotaRemaining: "{remaining} de {limit, plural, one {# proposta} many {# de propostas} other {# propostas}} restantes.",
  fields: {
    taskText: "Descreva a tarefa",
    taskTextPlaceholder: "Cole a tarefa, o briefing ou a vaga do cliente.",
    taskTextHelp: "Inclua o objetivo, as entregas, as restrições e o prazo, quando disponíveis.",
    freelancerPositioning: "Seu posicionamento",
    freelancerPositioningPlaceholder: "Descreva a experiência e os pontos fortes que fazem de você a pessoa certa.",
    freelancerPositioningHelp: "Use apenas afirmações que você pode sustentar—a proposta não vai inventar experiência.",
    toneLegend: "Estilo da proposta",
  },
  toneOptions: {
    warm: "Caloroso e pessoal",
    neutral: "Claro e profissional",
    firm: "Confiante e direto",
  },
  fieldNames: {
    taskText: "Descrição da tarefa",
    freelancerPositioning: "Seu posicionamento",
  },
  generate: {
    submit: "Gerar proposta",
    running: "Gerando sua proposta…",
    runFailed: "Algo deu errado ao gerar sua proposta. Tente novamente.",
    startAnother: "Criar outra proposta",
  },
};
