// Portuguese (generic) ProposalAI messages.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const pt: Shape<typeof en> = {
  title: "ProposalAI",
  quotaRemaining: "{remaining} de {limit, plural, one {# proposta} many {# de propostas} other {# propostas}} restantes.",
  fields: {
    taskText: "Descreva a tarefa",
    freelancerPositioning: "Seu posicionamento",
    tone: "Tom (opcional)",
    tonePlaceholder: "Padrão",
    language: "Idioma (opcional)",
  },
  fieldNames: {
    taskText: "Descrição da tarefa",
    freelancerPositioning: "Seu posicionamento",
    language: "Idioma",
  },
  validation: { languageFormat: 'O idioma deve ter o formato "en" ou "en-US".' },
  generate: {
    submit: "Gerar proposta",
    running: "Gerando sua proposta…",
    runFailed: "Algo deu errado ao gerar sua proposta. Tente novamente.",
  },
};
