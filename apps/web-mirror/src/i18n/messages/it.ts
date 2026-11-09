// Italian host messages (ICU); typographic ’ only. Register: formal "Lei" throughout. Instructions are
// the polite imperative ("Riprovi", "Copi", "Ricarichi la pagina"), never the infinitive or the
// informal "tu" imperative, so every product page reads the same way.
import type { Shape } from "../messageTypes";
import type { en } from "./en";

export const it: Shape<typeof en> = {
  language: { label: "Lingua" },
  nav: {
    label: "Strumenti",
    allTools: "Tutti gli strumenti",
    runInProgress: "È in corso un’esecuzione. Se esci, continuerà; un risultato riuscito utilizza un’esecuzione.",
  },
  loading: "Caricamento di {product}…",
  unavailable: "{product} non è disponibile al momento. Ricarichi la pagina.",
  quotaReserved: "Disponibili ora: {available}. In corso: {reserved}.",
  quotaExhausted: "Le esecuzioni di {product} a disposizione sono esaurite per ora.",
  resultFetchFailed: "Il risultato è pronto, ma non è stato possibile caricarlo. Riprovi.",
  starting: "Avvio in corso…",
  generating: "Generazione in corso…",
  identityUnavailable: "Non è stato possibile verificare la sua identità. Ricarichi la pagina e riprovi.",
  retry: "Riprovi",
  formLabel: "Modulo {product}",
  workspace: {
    inputTitle: "I suoi dati",
    previousDetails: "Risultato basato sui dati precedenti",
    backToInputs: "Torni ai dati",
    newTask: "Nuova attività",
    handoffOpening: "Apertura del passaggio successivo…",
    handoffStay: "Resti su questa pagina",
    handoffFailed: "Impossibile aprire il passaggio successivo. Riprovi.",
  },
  errors: {
    attachmentUnrecognized: "Non è stato possibile ripristinare questa sessione salvata. Riprova oppure scegli «Nuova attività» per aprire un modulo vuoto.",
    attachmentUnavailable: "Questa sessione non può essere aperta in questo strumento. Scegli «Nuova attività» per aprire un modulo vuoto.",
    quotaCapacityReserved: "La capacità è temporaneamente occupata. Riprova tra poco.",
    startFailed: "Impossibile avviare {product}. Riprovi.",
    timeout: "L’operazione richiede più tempo del previsto. Riprovi.",
    connectionLost: "Connessione persa durante l’attesa del risultato. Riprovi.",
    tryAgain: "Riprovi.",
  },
  result: {
    copy: "Copi",
    copying: "Copia in corso…",
    copied: "Copiato",
    copyFailed: "Impossibile copiare negli appunti. Copi manualmente il testo qui sopra.",
    selectText: "Selezioni il testo",
  },
  // Code review finding: maxLength made `{field}` the subject of "deve" (which
  // agrees in number: deve/devono) -- every message is now a label-colon-fragment instead, matching
  // `required`'s already-safe shape (normalized to "{field}: ..." order for consistency).
  validation: {
    required: "{field}: campo obbligatorio.",
    maxLength: "{field}: massimo {maxLength, plural, one {# carattere} many {# di caratteri} other {# caratteri}}.",
  },
};
