// Portuguese (generic) Client Update Writer messages.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";
import { pt as tone } from "../../shared/toneMessages/pt";

export const pt: Shape<typeof en> = {
  title: "Client Update Writer",
  tone,
  quotaRemaining: "{remaining} de {limit, plural, one {# execução do Client Update Writer} many {# de execuções do Client Update Writer} other {# execuções do Client Update Writer}} restantes.",
  modes: {
    legend: "Modo",
    update: "Atualização",
    reply_draft: "Rascunho de resposta",
    prepaid_request: "Pedido de pré-pagamento",
  },
  fields: {
    progressNotes: "Notas de progresso",
    clientMessage: "Mensagem do cliente",
    replyGoal: "Objetivo da resposta",
    billingNotes: "Notas de cobrança",
    billingAmount: "Valor",
    billingDueDate: "Data de vencimento (opcional)",
    tone: "Tom",
    tonePlaceholder: "Selecione um tom",
  },
  fieldNames: {
    progressNotes: "Notas de progresso",
    clientMessage: "Mensagem do cliente",
    replyGoal: "Objetivo da resposta",
    billingNotes: "Notas de cobrança",
    billingAmount: "Valor",
    billingDueDate: "Data de vencimento",
    tone: "Tom",
  },
  update: {
    submit: "Escrever atualização",
    running: "Escrevendo sua atualização…",
    runFailed: "Algo deu errado ao escrever sua atualização. Tente novamente.",
  },
  reply_draft: {
    submit: "Escrever resposta",
    running: "Escrevendo sua resposta…",
    runFailed: "Algo deu errado ao escrever sua resposta. Tente novamente.",
  },
  prepaid_request: {
    submit: "Escrever pedido",
    running: "Escrevendo seu pedido…",
    runFailed: "Algo deu errado ao escrever seu pedido. Tente novamente.",
  },
};
