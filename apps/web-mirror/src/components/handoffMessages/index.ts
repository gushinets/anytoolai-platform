// Backend preview values stay untranslated; these messages describe the surrounding consent UI.
// openResult applies to spent tokens with a queued target; previewFields labels only known preview keys.

import type { Locale, Shape } from "../../i18n";
import de from "./de.json";
import en from "./en.json";
import es from "./es.json";
import fr from "./fr.json";
import it from "./it.json";
import pt from "./pt.json";
import ru from "./ru.json";

export const HANDOFF_MESSAGES: Record<Locale, Shape<typeof en>> = { en, fr, it, de, es, ru, pt };
