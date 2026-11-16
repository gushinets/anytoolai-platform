// English defines message keys; tests enforce exact locale structure and ICU argument parity.
// Validation uses label-colon fragments: field names may be plural, so verbs must not agree with them.
// Keep German Sie and Italian Lei; avoid ASCII apostrophes before ICU placeholders.

import type { Locale } from "../locales";
import type { Shape } from "../messageTypes";
import de from "./de.json";
import en from "./en.json";
import es from "./es.json";
import fr from "./fr.json";
import it from "./it.json";
import pt from "./pt.json";
import ru from "./ru.json";

export type HostMessages = typeof en;

export const HOST_MESSAGES: Record<Locale, Shape<HostMessages>> = { en, fr, it, de, es, ru, pt };
