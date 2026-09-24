import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const es: Shape<typeof en> = {
  title: "AnytoolAI",
  lead: "Herramientas pequeñas para freelancers. Describa el trabajo y reciba un texto listo para enviar al cliente.",
  open: "Abrir",
  cards: {
    proposal_ai: {
      blurb: "Convierta el brief de un cliente y sus puntos fuertes en una propuesta lista para enviar.",
      sample: "Hola Dana, me encantaría ayudarle con el rediseño de su landing page. Dos rondas de revisiones, entrega en tres semanas. Hagamos una llamada breve para confirmar el alcance.",
    },
    client_update_writer: {
      blurb: "Escriba una actualización de progreso, responda a un mensaje del cliente o solicite un anticipo, con el tono que elija.",
      sample: "Actualización rápida: el rediseño de la página de inicio está terminado y listo para revisión el viernes. Sin bloqueos por ahora.",
      tags: {
        update: "Actualización",
        replyDraft: "Borrador de respuesta",
        prepaidRequest: "Solicitud de anticipo",
      },
    },
  },
};
