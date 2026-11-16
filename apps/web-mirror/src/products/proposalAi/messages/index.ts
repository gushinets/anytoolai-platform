// Descriptive tone labels are product-owned; wire values remain neutral|warm|firm.
// Validation field names can differ from visible input labels. Spanish is neutral, Portuguese generic.

import type { Locale, Shape } from "../../../i18n";
import de from "./de.json";
import en from "./en.json";
import es from "./es.json";
import fr from "./fr.json";
import it from "./it.json";
import pt from "./pt.json";
import ru from "./ru.json";

export const PROPOSAL_AI_MESSAGES: Record<Locale, Shape<typeof en>> = { en, fr, it, de, es, ru, pt };
