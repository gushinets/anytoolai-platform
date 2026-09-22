import type { Locale } from "../locales";
import type { Shape } from "../messageTypes";
import { de } from "./de";
import { en } from "./en";
import { es } from "./es";
import { fr } from "./fr";
import { it } from "./it";
import { pt } from "./pt";
import { ru } from "./ru";

export type HostMessages = typeof en;

export const HOST_MESSAGES: Record<Locale, Shape<HostMessages>> = { en, fr, it, de, es, ru, pt };
