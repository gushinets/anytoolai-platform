// German host messages (Sie-Form).
import type { Shape } from "../messageTypes";
import type { en } from "./en";

export const de: Shape<typeof en> = {
  language: { label: "Sprache" },
  loading: "{product} wird geladen…",
  unavailable: "{product} ist derzeit nicht verfügbar. Bitte laden Sie die Seite neu.",
  quotaExhausted: "Sie haben vorerst alle Ihre {product}-Durchläufe verbraucht.",
  resultFetchFailed: "Ihr Ergebnis ist fertig, konnte aber nicht geladen werden. Bitte versuchen Sie es erneut.",
  starting: "Wird gestartet…",
  generating: "Wird erstellt…",
  identityUnavailable: "Wir konnten Ihre Identität nicht überprüfen. Bitte laden Sie die Seite neu und versuchen Sie es erneut.",
  retry: "Erneut versuchen",
  errors: {
    startFailed: "{product} konnte nicht gestartet werden. Bitte versuchen Sie es erneut.",
    timeout: "Das dauert länger als erwartet. Bitte versuchen Sie es erneut.",
    connectionLost: "Die Verbindung ging beim Warten auf Ihr Ergebnis verloren. Bitte versuchen Sie es erneut.",
    tryAgain: "Bitte versuchen Sie es erneut.",
  },
  result: {
    copy: "Kopieren",
    copying: "Wird kopiert…",
    copied: "Kopiert",
    copyFailed: "Das Kopieren in die Zwischenablage ist fehlgeschlagen. Bitte kopieren Sie den obigen Text manuell.",
  },
  validation: {
    required: "{field} ist erforderlich.",
    outerWhitespace: "{field} darf nicht mit einem Leerzeichen beginnen oder enden.",
    maxLength: "{field} darf höchstens {maxLength, plural, one {# Zeichen} other {# Zeichen}} lang sein.",
  },
  tone: { neutral: "neutral", warm: "herzlich", firm: "bestimmt" },
};
