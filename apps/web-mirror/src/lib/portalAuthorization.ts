import { consumePortalCallback, exchangePortalSession, PlatformApiClient, preparePortalAuthorization, validatePortalReturnTarget } from "@anytoolai/ce-kit";
import { getRegisteredProduct } from "../products/registry";
import { installPortalSession, requirePortalAuthorization, synchronizePortalIdentity, tabStorage } from "./portalSession";

const CONTINUATION_KEY = "anytoolai.portal_continuation.v1";
export function validateReturnTarget(target: string): string | null {
  return validatePortalReturnTarget(target, (id) => getRegisteredProduct(id) !== null);
}

export function readPortalContinuation(): string | null {
  const target = tabStorage.getItem(CONTINUATION_KEY);
  return target === null ? null : validateReturnTarget(target);
}

export function rememberPortalContinuation(target: string): void {
  const validated = validateReturnTarget(target);
  if (!validated) throw new Error("portal_target_invalid");
  tabStorage.setItem(CONTINUATION_KEY, validated);
}

export async function beginPortalAuthorization(target: string): Promise<string> {
  const returnTarget = validateReturnTarget(target);
  const configured = process.env.NEXT_PUBLIC_PORTAL_AUTHORIZE_URL;
  if (!returnTarget || !configured) throw new Error("portal_authorization_invalid");
  const url = new URL(configured);
  if ((url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname))) ||
    url.username || url.password || url.search || url.hash || !/^\/(en|fr|it|de|es|ru|pt)\/backend\/authorize$/.test(url.pathname)) throw new Error("portal_authorization_invalid");
  synchronizePortalIdentity();
  if (!requirePortalAuthorization()) throw new Error("portal_storage_unavailable");
  const identity = synchronizePortalIdentity();
  if (!identity.custodyId) throw new Error("portal_storage_unavailable");
  tabStorage.setItem(CONTINUATION_KEY, returnTarget);
  const { state, challenge } = await preparePortalAuthorization(tabStorage, returnTarget, identity.custodyId);
  if (synchronizePortalIdentity().generation !== identity.generation) throw new Error("portal_authorization_invalid");
  url.searchParams.set("consumer_id", "platform-kernel");
  url.searchParams.set("state", state);
  url.searchParams.set("code_challenge", challenge);
  url.searchParams.set("code_challenge_method", "S256");
  return url.href;
}

export async function completePortalAuthorization(fragment: string): Promise<string> {
  const identity = synchronizePortalIdentity();
  if (!identity.custodyId) throw new Error("portal_storage_unavailable");
  const generation = identity.generation;
  const callback = consumePortalCallback(tabStorage, fragment);
  if (!callback || callback.authorization.custodyId !== identity.custodyId || !validateReturnTarget(callback.authorization.returnTarget)) throw new Error("portal_callback_invalid");
  const result = await exchangePortalSession(new PlatformApiClient({ baseUrl: window.location.origin }), callback.code, callback.authorization.verifier);
  // Another document in this tab may change custody while this document is suspended.
  const current = synchronizePortalIdentity();
  if (!result.ok || current.generation !== generation) throw new Error("portal_exchange_failed");
  installPortalSession(result.value);
  tabStorage.removeItem(CONTINUATION_KEY);
  return callback.authorization.returnTarget;
}
