// German Client Update Writer messages (Sie-Form).
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";
import { de as tone } from "../../shared/toneMessages/de";

export const de: Shape<typeof en> = {
  title: "Client Update Writer",
  tone,
  quotaRemaining: "{remaining} von {limit, plural, one {# Client-Update-Writer-Durchlauf} other {# Client-Update-Writer-Durchläufen}} verbleibend.",
  modes: {
    legend: "Modus",
    update: "Update",
    reply_draft: "Antwortentwurf",
    prepaid_request: "Vorauszahlungsanfrage",
  },
  fields: {
    progressNotes: "Fortschrittsnotizen",
    clientMessage: "Nachricht des Kunden",
    replyGoal: "Ziel der Antwort",
    billingNotes: "Abrechnungsnotizen",
    billingAmount: "Betrag",
    billingDueDate: "Fälligkeitsdatum (optional)",
    tone: "Tonalität",
    tonePlaceholder: "Tonalität auswählen",
  },
  fieldNames: {
    progressNotes: "Die Fortschrittsnotizen",
    clientMessage: "Die Nachricht des Kunden",
    replyGoal: "Das Ziel der Antwort",
    billingNotes: "Die Abrechnungsnotizen",
    billingAmount: "Der Betrag",
    billingDueDate: "Das Fälligkeitsdatum",
    tone: "Die Tonalität",
  },
  update: {
    submit: "Update schreiben",
    running: "Ihr Update wird geschrieben…",
    runFailed: "Beim Schreiben Ihres Updates ist etwas schiefgelaufen. Bitte versuchen Sie es erneut.",
  },
  reply_draft: {
    submit: "Antwort schreiben",
    running: "Ihre Antwort wird geschrieben…",
    runFailed: "Beim Schreiben Ihrer Antwort ist etwas schiefgelaufen. Bitte versuchen Sie es erneut.",
  },
  prepaid_request: {
    submit: "Anfrage schreiben",
    running: "Ihre Anfrage wird geschrieben…",
    runFailed: "Beim Schreiben Ihrer Anfrage ist etwas schiefgelaufen. Bitte versuchen Sie es erneut.",
  },
};
