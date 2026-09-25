import type { Locale, Shape } from "../../i18n";
import { de } from "./de";
import { en } from "./en";
import { es } from "./es";
import { fr } from "./fr";
import { it } from "./it";
import { pt } from "./pt";
import { ru } from "./ru";

export const HOME_MESSAGES: Record<Locale, Shape<typeof en>> = { en, fr, it, de, es, ru, pt };
