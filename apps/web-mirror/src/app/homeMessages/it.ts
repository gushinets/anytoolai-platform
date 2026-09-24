import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const it: Shape<typeof en> = {
  title: "AnytoolAI",
  lead: "Piccoli strumenti per freelance. Descrivi il lavoro e ottieni un testo pronto da inviare al cliente.",
  open: "Apri",
  cards: {
    proposal_ai: {
      blurb: "Trasforma il brief di un cliente e i tuoi punti di forza in una proposta pronta da inviare.",
      sample: "Ciao Dana, mi farebbe piacere aiutarti con il restyling della tua landing page. Due giri di revisioni, consegna in tre settimane. Facciamo una breve chiamata per confermare l'ambito.",
    },
    client_update_writer: {
      blurb: "Scrivi un aggiornamento sull'avanzamento, una risposta a un messaggio del cliente o una richiesta di anticipo, con il tono che preferisci.",
      sample: "Aggiornamento rapido: il restyling della homepage è completato e pronto per la revisione entro venerdì. Nessun blocco per ora.",
      tags: {
        update: "Aggiornamento",
        replyDraft: "Bozza di risposta",
        prepaidRequest: "Richiesta di anticipo",
      },
    },
  },
};
