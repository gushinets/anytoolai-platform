import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const pt: Shape<typeof en> = {
  title: "AnytoolAI",
  lead: "Pequenas ferramentas para freelancers. Descreva o trabalho e receba um texto pronto para enviar ao cliente.",
  open: "Abrir",
  cards: {
    proposal_ai: {
      blurb: "Transforme o briefing de um cliente e seus pontos fortes em uma proposta pronta para enviar.",
      sample: "Olá Dana, ficarei feliz em ajudar com o redesign da sua landing page. Duas rodadas de revisões, entrega em três semanas. Vamos marcar uma ligação rápida para confirmar o escopo.",
    },
    client_update_writer: {
      blurb: "Escreva uma atualização de progresso, uma resposta a uma mensagem do cliente ou um pedido de adiantamento, no tom que você escolher.",
      sample: "Atualização rápida: o redesign da página inicial está concluído e pronto para revisão até sexta-feira. Sem bloqueios por enquanto.",
      tags: {
        update: "Atualização",
        replyDraft: "Rascunho de resposta",
        prepaidRequest: "Pedido de adiantamento",
      },
    },
  },
};
