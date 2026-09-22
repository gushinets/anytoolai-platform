// Spanish (neutral) host messages; keys mirror en.ts.
import type { Shape } from "../messageTypes";
import type { en } from "./en";

export const es: Shape<typeof en> = {
  language: { label: "Idioma" },
  loading: "Cargando {product}…",
  unavailable: "{product} no está disponible en este momento. Recargue la página.",
  quotaExhausted: "Ha agotado todas sus ejecuciones de {product} por ahora.",
  resultFetchFailed: "Su resultado está listo, pero no pudimos cargarlo. Inténtelo de nuevo.",
  starting: "Iniciando…",
  generating: "Generando…",
  identityUnavailable: "No pudimos verificar su identidad. Recargue la página e inténtelo de nuevo.",
  retry: "Reintentar",
  errors: {
    startFailed: "No se pudo iniciar {product}. Inténtelo de nuevo.",
    timeout: "Esto está tardando más de lo esperado. Inténtelo de nuevo.",
    connectionLost: "Se perdió la conexión mientras esperaba su resultado. Inténtelo de nuevo.",
    tryAgain: "Inténtelo de nuevo.",
  },
  result: {
    copy: "Copiar",
    copying: "Copiando…",
    copied: "Copiado",
    copyFailed: "No se pudo copiar al portapapeles. Copie el texto de arriba manualmente.",
  },
  validation: {
    required: "{field}: este campo es obligatorio.",
    outerWhitespace: "{field}: no debe empezar ni terminar con espacios en blanco.",
    maxLength: "{field}: debe tener como máximo {maxLength, plural, one {# carácter} many {# de caracteres} other {# caracteres}}.",
  },
  tone: { neutral: "neutral", warm: "cálido", firm: "firme" },
};
