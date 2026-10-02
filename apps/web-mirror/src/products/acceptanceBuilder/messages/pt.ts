import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const pt: Shape<typeof en> = {
  title: "Acceptance Builder",
  description: "Transforme o briefing de um cliente em critérios de aceitação, ou confira o trabalho concluído com o briefing.",
  quotaRemaining: "{remaining} de {limit, plural, one {# execução} other {# execuções}} restantes.",
  modes: {
    legend: "Modo",
    draft: "Redigir critérios",
    check: "Conferir entrega",
  },
  fields: {
    briefText: "Briefing do cliente",
    briefTextPlaceholder: "Cole o briefing, o pedido ou a vaga do cliente.",
    briefTextHelp: "Cole o briefing como está.",
    deliverableText: "Trabalho concluído",
    deliverableTextPlaceholder: "Cole o texto do trabalho concluído.",
    deliverableTextHelp: "Cole o texto que você pretende entregar.",
  },
  draft: {
    submit: "Redigir critérios",
    running: "Redigindo os critérios de aceitação…",
    runFailed: "Algo deu errado ao redigir os critérios. Tente novamente.",
    resultTitle: "Critérios de aceitação",
    placeholder: "Seus critérios de aceitação aparecerão aqui depois de redigidos.",
    regenerate: "Redigir novamente",
  },
  check: {
    submit: "Conferir entrega",
    running: "Conferindo sua entrega…",
    runFailed: "Algo deu errado ao conferir a entrega. Tente novamente.",
    resultTitle: "Conferência da entrega",
    placeholder: "Sua conferência aparecerá aqui depois de executada.",
    regenerate: "Conferir novamente",
  },
  result: {
    verdictScope: "O veredito se baseia em quatro critérios gerais de revisão, não item a item nos critérios listados abaixo.",
    recap: "Resumo narrativo (somente exibição, não copiado)",
  },
};
