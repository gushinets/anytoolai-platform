import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const pt: Shape<typeof en> = {
  title: "AnytoolAI",
  lead: "Pequenas ferramentas para freelancers. Descreva o trabalho e receba um texto pronto para enviar ao cliente.",
  open: "Abrir",
  cards: {
    proposal_ai: {
      blurb: "Transforme o briefing de um cliente e os seus pontos fortes numa proposta pronta a enviar.",
      sample: "Olá Dana, terei muito gosto em ajudar com o redesign da sua landing page. Duas rondas de revisões, entrega em três semanas. Vamos marcar uma chamada rápida para confirmar o âmbito.",
    },
    client_update_writer: {
      blurb: "Escreva uma atualização de progresso, uma resposta a uma mensagem do cliente ou um pedido de adiantamento, no tom que escolher.",
      sample: "Atualização rápida: o redesign da página inicial está concluído e pronto para revisão até sexta-feira. Sem bloqueios por agora.",
      tags: {
        update: "Atualização",
        replyDraft: "Rascunho de resposta",
        prepaidRequest: "Pedido de adiantamento",
      },
    },
  },
};
