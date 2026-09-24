import type { Metadata } from "next";
import type { ReactNode } from "react";
import { getRegisteredProduct } from "../../../products/registry";

type ProductLayoutProps = { children: ReactNode; params: Promise<{ productId: string }> };

// The page itself is a client component, so the tab title comes from this server layout. Product
// names are the same in every locale, so the English title is the one for all of them.
export async function generateMetadata({ params }: Pick<ProductLayoutProps, "params">): Promise<Metadata> {
  const { productId } = await params;
  const product = getRegisteredProduct(productId);
  return product ? { title: product.messages.en.title } : {};
}

export default function ProductLayout({ children }: Pick<ProductLayoutProps, "children">) {
  return children;
}
