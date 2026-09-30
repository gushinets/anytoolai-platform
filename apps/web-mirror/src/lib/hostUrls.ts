/** The web host's product and handoff URL layout, in one place: the product route, the
 * `?session=` attach parameter, and the consent base URL under an optional basePath. */
export const ATTACH_SESSION_PARAM = "session";

/** `/products/{productId}?session={id}`: the product page attached to an already-queued session. */
export function productAttachPath(productId: string, scenarioSessionId: string): string {
  return `/products/${encodeURIComponent(productId)}?${ATTACH_SESSION_PARAM}=${encodeURIComponent(scenarioSessionId)}`;
}

/** Origin plus basePath (everything before `/products/`) of a product page location. */
export function webBaseUrlFromProductLocation({ origin, pathname }: { origin: string; pathname: string }): string {
  return origin + pathname.split("/products/")[0];
}
