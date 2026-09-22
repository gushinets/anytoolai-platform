import type { Locale } from "../../../i18n";
import type { Shape } from "../../../i18n/messageTypes";
import { de } from "./de";
import { en } from "./en";
import { es } from "./es";
import { fr } from "./fr";
import { it } from "./it";
import { pt } from "./pt";
import { ru } from "./ru";

/**
 * `neutral|warm|firm` labels, shared by every product whose input schema declares this `tone`
 * enum -- centralized here (one translation per locale, not one per product) because it genuinely
 * is shared vocabulary, but kept OUT of host `i18n/messages/` (code review finding): host owns
 * generic runtime/result/error/validation copy, never product meaning, and `neutral|warm|firm` is
 * exactly that -- a product-owned wire enum's visible labels. Each product's own message tree
 * spreads this in under its own `tone` key (see `products/proposalAi/messages/en.ts`), so
 * `tone.tsx`'s `useProductT()` resolves it from whichever product is actually active, and a future
 * product with a differently-meaning `tone`-shaped enum needs no change here or in host.
 */
export const TONE_MESSAGES: Record<Locale, Shape<typeof en>> = { en, fr, it, de, es, ru, pt };
