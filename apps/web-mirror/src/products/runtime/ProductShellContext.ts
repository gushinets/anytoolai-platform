import { createContext } from "react";
import type { ProductQuotaStore } from "./quotaAdmission";

/** Shared page lifetime state and run-page reporting. */
export type ProductShell = {
  quotaStore?: ProductQuotaStore;
  /** True while a run is in flight (see `busy` in `ProductRunPage`); the shell warns before leaving. */
  reportBusy: (busy: boolean) => void;
};

/** Non-null when the page shell owns the product title, language selector and the one `<main>`. */
export const ProductShellContext = createContext<ProductShell | null>(null);
