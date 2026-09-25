import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const pt: Shape<typeof en> = {
  title: "Revisar a transferência",
  loading: "Carregando a transferência…",
  notFound: "Este link de transferência não é válido.",
  loadFailed: "Algo deu errado ao carregar esta transferência. Tente novamente.",
  retry: "Tentar novamente",
  actionFailed: "Não foi possível concluir a ação. Tente novamente.",
  fields: {
    from: "De",
    to: "Para",
    expires: "Expira em",
    status: "Status",
  },
  accept: "Aceitar",
  decline: "Recusar",
  accepting: "Aceitando…",
  declining: "Recusando…",
  status: {
    waiting: "Aguardando sua decisão",
    accepted: "Aceita",
    declined: "Recusada",
    expired: "Expirada",
    failed: "Falhou",
  },
};
