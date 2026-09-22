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
  validation: {
    required: "Campo obbligatorio: {field}.",
    outerWhitespace: "{field} non deve iniziare né terminare con spazi.",
    maxLength: "{field} non deve superare {maxLength, plural, one {# carattere} many {# di caratteri} other {# caratteri}}.",
  },
  tone: { neutral: "neutro", warm: "cordiale", firm: "fermo" },
};
