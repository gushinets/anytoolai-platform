import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const es: Shape<typeof en> = {
  title: "Revisar la transferencia",
  loading: "Cargando la transferencia…",
  notFound: "Este enlace de transferencia no es válido.",
  loadFailed: "Algo salió mal al cargar esta transferencia. Inténtelo de nuevo.",
  retry: "Reintentar",
  actionFailed: "No se pudo completar la acción. Inténtelo de nuevo.",
  fields: {
    from: "De",
    to: "Para",
    expires: "Caduca",
    status: "Estado",
  },
  // Shown on a spent (accepted/consumed) token that still names the queued target session.
  openResult: "Abrir el resultado",
  accept: "Aceptar",
  decline: "Rechazar",
  accepting: "Aceptando…",
  declining: "Rechazando…",
  status: {
    waiting: "Esperando su decisión",
    accepted: "Aceptada",
    declined: "Rechazada",
    expired: "Caducada",
    failed: "Fallida",
  },
  // Labels for the backend's known preview keys (`handoffs.yaml` `preview_mapping`); any other key is shown as sent.
  previewFields: {
    summary: "Resumen",
    missing_fields: "Datos que faltan",
  },
};
