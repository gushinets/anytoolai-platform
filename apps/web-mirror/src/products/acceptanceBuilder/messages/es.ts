import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const es: Shape<typeof en> = {
  title: "Acceptance Builder",
  description: "Convierta el brief de un cliente en criterios de aceptación, o compruebe el trabajo terminado frente al brief.",
  quotaRemaining: "{remaining} de {limit, plural, one {# ejecución} other {# ejecuciones}} restantes.",
  modes: {
    legend: "Modo",
    draft: "Redactar criterios",
    check: "Comprobar entregable",
  },
  fields: {
    briefText: "Brief del cliente",
    briefTextPlaceholder: "Pegue el brief, la solicitud o la oferta del cliente.",
    briefTextHelp: "Pegue el brief tal cual.",
    deliverableText: "Trabajo terminado",
    deliverableTextPlaceholder: "Pegue el texto del trabajo terminado.",
    deliverableTextHelp: "Pegue el texto que piensa entregar.",
  },
  draft: {
    submit: "Redactar criterios",
    running: "Redactando los criterios de aceptación…",
    runFailed: "Algo salió mal al redactar los criterios. Inténtelo de nuevo.",
    resultTitle: "Criterios de aceptación",
    placeholder: "Sus criterios de aceptación aparecerán aquí tras redactarlos.",
    regenerate: "Redactar de nuevo",
  },
  check: {
    submit: "Comprobar entregable",
    running: "Comprobando su entregable…",
    runFailed: "Algo salió mal al comprobar el entregable. Inténtelo de nuevo.",
    resultTitle: "Comprobación del entregable",
    placeholder: "Su comprobación aparecerá aquí tras ejecutarla.",
    regenerate: "Comprobar de nuevo",
  },
  result: {
    verdictScope: "El veredicto se basa en cuatro criterios generales de revisión, no punto por punto en los criterios listados abajo.",
    recap: "Resumen narrativo (solo visualización, no se copia)",
  },
};
