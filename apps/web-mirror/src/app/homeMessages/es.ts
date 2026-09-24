import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const es: Shape<typeof en> = {
  title: "AnytoolAI",
  lead: "Herramientas pequeñas para freelancers. Describe el trabajo y recibe un texto listo para enviar al cliente.",
  open: "Abrir",
  cards: {
    proposal_ai: {
      blurb: "Convierte el brief de un cliente y tus puntos fuertes en una propuesta lista para enviar.",
      sample: "Hola Dana, me encantaría ayudarte con el rediseño de tu landing page. Dos rondas de revisiones, entrega en tres semanas. Hagamos una llamada breve para confirmar el alcance.",
    },
    client_update_writer: {
      blurb: "Escribe una actualización de progreso, responde a un mensaje del cliente o pide un anticipo, con el tono que elijas.",
      sample: "Actualización rápida: el rediseño de la página de inicio está terminado y listo para revisión el viernes. Sin bloqueos por ahora.",
      tags: {
        update: "Actualización",
        replyDraft: "Borrador de respuesta",
        prepaidRequest: "Solicitud de anticipo",
      },
    },
  },
};
