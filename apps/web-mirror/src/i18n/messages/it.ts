// Italian host messages (ICU); typographic ’ only.
import type { Shape } from "../messageTypes";
import type { en } from "./en";

export const it: Shape<typeof en> = {
  language: { label: "Lingua" },
  loading: "Caricamento di {product}…",
  unavailable: "{product} non è disponibile al momento. Ricaricare la pagina.",
  quotaExhausted: "Le esecuzioni di {product} a disposizione sono esaurite per ora.",
  resultFetchFailed: "Il risultato è pronto, ma non è stato possibile caricarlo. Riprovare.",
  starting: "Avvio in corso…",
  generating: "Generazione in corso…",
  identityUnavailable: "Non è stato possibile verificare la sua identità. Ricaricare la pagina e riprovare.",
  retry: "Riprova",
  errors: {
    startFailed: "Impossibile avviare {product}. Riprovare.",
    timeout: "L’operazione richiede più tempo del previsto. Riprovare.",
    connectionLost: "Connessione persa durante l’attesa del risultato. Riprovare.",
    tryAgain: "Riprovare.",
  },
  result: {
    copy: "Copia",
    copying: "Copia in corso…",
    copied: "Copiato",
    copyFailed: "Impossibile copiare negli appunti. Copiare manualmente il testo qui sopra.",
  },
  // Code review finding: outerWhitespace/maxLength made `{field}` the subject of "deve" (which
  // agrees in number: deve/devono) -- every message is now a label-colon-fragment instead, matching
  // `required`'s already-safe shape (normalized to "{field}: ..." order for consistency).
  validation: {
    required: "{field}: campo obbligatorio.",
    outerWhitespace: "{field}: niente spazi all’inizio o alla fine.",
    maxLength: "{field}: massimo {maxLength, plural, one {# carattere} many {# di caratteri} other {# caratteri}}.",
  },
};
