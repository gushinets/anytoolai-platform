import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const it: Shape<typeof en> = {
  title: "AnytoolAI",
  lead: "Piccoli strumenti per freelance. Descriva il lavoro e ottenga un testo pronto da inviare al cliente.",
  open: "Apri",
  cards: {
    proposal_ai: {
      blurb: "Trasformi il brief di un cliente e i suoi punti di forza in una proposta pronta da inviare.",
      sample: "Buongiorno Dana, mi farebbe piacere aiutarla con il restyling della sua landing page. Due giri di revisioni, consegna in tre settimane. Facciamo una breve chiamata per confermare l'ambito.",
    },
    client_update_writer: {
      blurb: "Scriva un aggiornamento sull'avanzamento, una risposta a un messaggio del cliente o una richiesta di anticipo, con il tono che preferisce.",
      sample: "Aggiornamento rapido: il restyling della homepage è completato e pronto per la revisione entro venerdì. Nessun blocco per ora.",
      tags: {
        update: "Aggiornamento",
        replyDraft: "Bozza di risposta",
        prepaidRequest: "Richiesta di anticipo",
      },
    },
  },
};
