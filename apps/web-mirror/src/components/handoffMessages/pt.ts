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
  // Shown on a spent (accepted/consumed) token that still names the queued target session.
  openResult: "Abrir o resultado",
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
  // Labels for the backend's known preview keys (`handoffs.yaml` `preview_mapping`); any other key is shown as sent.
  previewFields: {
    summary: "Resumo",
    missing_fields: "Informações em falta",
  },
};
