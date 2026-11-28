import type { Locale, Shape } from "../../../i18n";
import type { IssueCategory } from "../parseBriefDecoder";
import de from "./de.json";
import en from "./en.json";
import es from "./es.json";
import fr from "./fr.json";
import it from "./it.json";
import pt from "./pt.json";
import ru from "./ru.json";

export const BRIEF_DECODER_MESSAGES: Record<Locale, Shape<typeof en> & {
  categories: Record<IssueCategory, string>;
}> = { en, fr, it, de, es, ru, pt };
