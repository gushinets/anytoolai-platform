import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const de: Shape<typeof en> = {
  title: "AnytoolAI",
  lead: "Kleine Werkzeuge für Freelancer. Beschreibe den Auftrag und erhalte einen Text, den du direkt an den Kunden senden kannst.",
  open: "Öffnen",
  cards: {
    proposal_ai: {
      blurb: "Mach aus dem Briefing deines Kunden und deinen Stärken ein Angebot, das sofort versandfertig ist.",
      sample: "Hallo Dana, ich helfe dir gern beim Redesign deiner Landingpage. Zwei Korrekturrunden, Lieferung in drei Wochen. Lass uns kurz telefonieren, um den Umfang zu klären.",
    },
    client_update_writer: {
      blurb: "Schreibe ein Status-Update, eine Antwort auf eine Kundennachricht oder eine Vorauszahlungsanfrage im gewünschten Ton.",
      sample: "Kurzes Update: Das Redesign der Startseite ist fertig und liegt bis Freitag zur Prüfung bereit. Bisher keine Blocker.",
      tags: {
        update: "Update",
        replyDraft: "Antwortentwurf",
        prepaidRequest: "Vorauszahlung",
      },
    },
  },
};
