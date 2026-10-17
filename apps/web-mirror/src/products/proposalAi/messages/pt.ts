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
    freelancerPositioning: "Sua experiência e pontos fortes",
    freelancerPositioningPlaceholder: "Descreva a experiência e os pontos fortes que fazem de você a pessoa certa.",
    freelancerPositioningHelp: "A proposta se baseia apenas no que você escrever aqui. Informe fatos verificáveis: ferramentas, casos, resultados.",
    toneLegend: "Estilo da proposta",
    required: "obrigatório",
    languageLabel: "Idioma da proposta",
    languageHelp: "Não é o idioma da interface. Por padrão, a proposta é escrita no idioma da tarefa.",
    languageAuto: "Como na tarefa",
    counterNear: "Você está perto do limite de {max} caracteres.",
    counterOver: "Limite de {max} caracteres excedido.",
  },
  toneOptions: {
    warm: "Caloroso e pessoal",
    neutral: "Claro e profissional",
    firm: "Confiante e direto",
  },
  fieldNames: {
    taskText: "Descrição da tarefa",
    freelancerPositioning: "Sua experiência e pontos fortes",
  },
  result: {
    gapsTitle: "O que sua experiência não cobre",
    gapsHint: "A proposta não afirma isso. Complemente por conta própria ou não mencione.",
  },
  generate: {
    submit: "Gerar proposta",
    running: "Gerando sua proposta…",
    runFailed: "Algo deu errado ao gerar sua proposta. Tente novamente.",
    resultTitle: "Proposta",
    placeholder: "Sua proposta aparecerá aqui após a geração.",
    regenerate: "Gerar proposta novamente",
  },
};
