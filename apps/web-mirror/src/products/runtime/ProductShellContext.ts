import { createContext } from "react";

/** What a product's run page reports up to the page shell that hosts it. */
export type ProductShell = {
  /** True while a run is in flight (see `busy` in `ProductRunPage`); the shell warns before leaving. */
  reportBusy: (busy: boolean) => void;
};

/** Non-null when the page shell owns the product title, language selector and the one `<main>`. */
export const ProductShellContext = createContext<ProductShell | null>(null);
