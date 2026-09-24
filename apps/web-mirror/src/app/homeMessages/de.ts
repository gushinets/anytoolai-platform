import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const de: Shape<typeof en> = {
  title: "AnytoolAI",
  lead: "Kleine Werkzeuge für Freelancer. Beschreiben Sie den Auftrag und erhalten Sie einen Text, den Sie direkt an den Kunden senden können.",
  open: "Öffnen",
  cards: {
    proposal_ai: {
      blurb: "Machen Sie aus dem Briefing Ihres Kunden und Ihren Stärken ein Angebot, das sofort versandfertig ist.",
      sample: "Hallo Dana, ich helfe Ihnen gern beim Redesign Ihrer Landingpage. Zwei Korrekturrunden, Lieferung in drei Wochen. Lassen Sie uns kurz telefonieren, um den Umfang zu klären.",
    },
    client_update_writer: {
      blurb: "Schreiben Sie ein Status-Update, eine Antwort auf eine Kundennachricht oder eine Vorauszahlungsanfrage im gewünschten Ton.",
      sample: "Kurzes Update: Das Redesign der Startseite ist fertig und liegt bis Freitag zur Prüfung bereit. Bisher keine Blocker.",
      tags: {
        update: "Update",
        replyDraft: "Antwortentwurf",
        prepaidRequest: "Vorauszahlung",
      },
    },
  },
};
