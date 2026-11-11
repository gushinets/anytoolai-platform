// Directory blurbs and output samples, independent of each product form’s wording.

import type { Locale, Shape } from "../../i18n";
import de from "./de.json";
import en from "./en.json";
import es from "./es.json";
import fr from "./fr.json";
import it from "./it.json";
import pt from "./pt.json";
import ru from "./ru.json";

export const HOME_MESSAGES: Record<Locale, Shape<typeof en>> = { en, fr, it, de, es, ru, pt };
