// German host messages (Sie-Form).
import type { Shape } from "../messageTypes";
import type { en } from "./en";

export const de: Shape<typeof en> = {
  language: { label: "Sprache" },
  nav: {
    label: "Tools",
    allTools: "Alle Tools",
    runInProgress: "Ein Durchlauf läuft. Wenn du gehst, wird er fortgesetzt; ein erfolgreiches Ergebnis verbraucht einen Durchlauf.",
  },
  loading: "{product} wird geladen…",
  unavailable: "{product} ist derzeit nicht verfügbar. Bitte laden Sie die Seite neu.",
  quotaReserved: "Jetzt verfügbar: {available}. In Bearbeitung: {reserved}.",
  quotaExhausted: "Sie haben vorerst alle Ihre {product}-Durchläufe verbraucht.",
  resultFetchFailed: "Ihr Ergebnis ist fertig, konnte aber nicht geladen werden. Bitte versuchen Sie es erneut.",
  starting: "Wird gestartet…",
  generating: "Wird erstellt…",
  identityUnavailable: "Wir konnten Ihre Identität nicht überprüfen. Bitte laden Sie die Seite neu und versuchen Sie es erneut.",
  retry: "Erneut versuchen",
  formLabel: "{product}-Formular",
  workspace: {
    inputTitle: "Ihre Angaben",
    previousDetails: "Mit vorherigen Angaben erstellt",
    backToInputs: "Zurück zu den Angaben",
    newTask: "Neue Aufgabe",
    handoffOpening: "Der nächste Schritt wird geöffnet…",
    handoffStay: "Auf dieser Seite bleiben",
    handoffFailed: "Der nächste Schritt konnte nicht geöffnet werden. Bitte versuchen Sie es erneut.",
  },
  errors: {
    attachmentUnrecognized: "Diese gespeicherte Sitzung konnte nicht wiederhergestellt werden. Versuchen Sie es erneut oder wählen Sie „Neue Aufgabe“, um ein leeres Formular zu öffnen.",
    attachmentUnavailable: "Diese Sitzung kann in diesem Tool nicht geöffnet werden. Wählen Sie „Neue Aufgabe“, um ein leeres Formular zu öffnen.",
    quotaCapacityReserved: "Die Kapazität ist vorübergehend belegt. Bitte versuche es gleich noch einmal.",
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
    selectText: "Text auswählen",
  },
  // Code review finding: `{field}` (e.g. "Die Fortschrittsnotizen", plural) can no longer be the
  // grammatical subject of an agreeing verb ("ist"/"sind", "darf"/"dürfen") -- every message is now
  // a label-colon-fragment, none of which needs a verb at all.
  validation: {
    required: "{field}: erforderlich.",
    maxLength: "{field}: höchstens {maxLength, plural, one {# Zeichen} other {# Zeichen}}.",
  },
};
