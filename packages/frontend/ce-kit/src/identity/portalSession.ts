import type { components } from "../api/generated/platformApi";
import { isRecord } from "../api/parsing";
import { requestAndParse, type PlatformApiClient, type PlatformApiResult } from "../api/client";

type ExchangeResponse = components["schemas"]["PortalExchangeResponse"];
export type PortalOwner = { tenantId: string; region: string; userId: string };
export type PortalSession = { owner: PortalOwner; consumerId: string; consumerPolicyRevision: number; accessToken: string; expiresAt: string };
export type TabStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;
export const PORTAL_SESSION_KEY = "anytoolai.portal_session.v1";
const AUTHORIZATION_KEY = "anytoolai.portal_authorization.v1";
const RANDOM_BYTES = 32;

export function samePortalOwner(a: PortalOwner, b: PortalOwner): boolean {
  return a.tenantId === b.tenantId && a.region === b.region && a.userId === b.userId;
}

export function parsePortalOwner(value: unknown): PortalOwner | null {
  if (!isRecord(value) || typeof value.tenantId !== "string" || !value.tenantId ||
    typeof value.region !== "string" || !value.region || typeof value.userId !== "string" ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.userId)) return null;
  return { tenantId: value.tenantId, region: value.region, userId: value.userId };
}

export function parsePortalExchange(value: unknown): PortalSession | null {
  if (!isRecord(value) || value.schema_version !== 2 || value.token_type !== "Bearer" ||
    typeof value.access_token !== "string" || !/^[A-Za-z0-9_-]{43,512}$/.test(value.access_token) ||
    typeof value.expires_at !== "string" || !/Z$|[+]00:00$/.test(value.expires_at) ||
    !Number.isFinite(Date.parse(value.expires_at))) return null;
  if (value.consumer_id !== "platform-kernel" || !Number.isSafeInteger(value.consumer_policy_revision) ||
    typeof value.consumer_policy_revision !== "number" || value.consumer_policy_revision < 1) return null;
  const owner = parsePortalOwner({ tenantId: value.tenant_id, region: value.region, userId: value.user_id });
  if (!owner) return null;
  // Compile-time drift check against the backend-owned exchange contract.
  const wire: ExchangeResponse = {
    consumer_id: value.consumer_id, consumer_policy_revision: value.consumer_policy_revision,
    schema_version: value.schema_version, token_type: value.token_type, access_token: value.access_token,
    tenant_id: owner.tenantId, region: owner.region, user_id: owner.userId, expires_at: value.expires_at,
  };
  return { owner, consumerId: wire.consumer_id, consumerPolicyRevision: wire.consumer_policy_revision, accessToken: wire.access_token, expiresAt: wire.expires_at };
}

export function exchangePortalSession(client: PlatformApiClient, code: string, verifier: string): Promise<PlatformApiResult<PortalSession>> {
  return requestAndParse(client, {
    method: "POST", path: "/v1/portal-session/exchange", body: { code, code_verifier: verifier },
  }, parsePortalExchange, "Portal session response was invalid.");
}

export function writePortalSession(storage: TabStorage, session: PortalSession): void {
  storage.setItem(PORTAL_SESSION_KEY, JSON.stringify({ version: 2, ...session }));
}

export function readPortalSession(storage: TabStorage): PortalSession | null {
  const raw = storage.getItem(PORTAL_SESSION_KEY);
  if (!raw) return null;
  const value: unknown = JSON.parse(raw);
  if (!isRecord(value) || value.version !== 2) throw new Error("portal_storage_invalid");
  const session = parsePortalExchange({ schema_version: 2, consumer_id: value.consumerId, consumer_policy_revision: value.consumerPolicyRevision, token_type: "Bearer", access_token: value.accessToken,
    expires_at: value.expiresAt, tenant_id: isRecord(value.owner) ? value.owner.tenantId : undefined,
    region: isRecord(value.owner) ? value.owner.region : undefined, user_id: isRecord(value.owner) ? value.owner.userId : undefined });
  if (!session) throw new Error("portal_storage_invalid");
  return session;
}

function base64url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Product registration belongs to the host. Only its registered local paths pass this boundary. */
export function validatePortalReturnTarget(target: string, isRegistered: (productId: string) => boolean): string | null {
  if (!target.startsWith("/") || target.startsWith("//") || /[\\#]/.test(target) || Array.from(target).some((char) => char.charCodeAt(0) <= 32)) return null;
  const url = new URL(target, "https://kernel.invalid");
  const product = /^\/products\/([a-z0-9_]+)$/.exec(url.pathname);
  if (product && isRegistered(product[1])) {
    for (const [key, value] of url.searchParams) {
      if (!["session", "scenario", "paid"].includes(key) || url.searchParams.getAll(key).length !== 1 ||
        (key === "paid" && value !== "1") ||
        !/^[A-Za-z0-9_.-]{1,128}$/.test(value)) return null;
    }
    return url.pathname + url.search;
  }
  if (/^\/handoff\/[A-Za-z0-9_-]{1,512}$/.test(url.pathname) && (!url.search || url.search === "?paid=1")) return url.pathname + url.search;
  return null;
}

export type PortalAuthorization = { state: string; verifier: string; returnTarget: string; custodyId: string };

export async function preparePortalAuthorization(storage: TabStorage, returnTarget: string, custodyId: string, cryptoApi: Crypto = crypto): Promise<{ state: string; challenge: string }> {
  // No insecure randomness fallback: PKCE needs a secure browser context.
  const state = base64url(cryptoApi.getRandomValues(new Uint8Array(RANDOM_BYTES)));
  const verifier = base64url(cryptoApi.getRandomValues(new Uint8Array(RANDOM_BYTES)));
  // Persist before yielding: a suspended older launch must not overwrite a newer authorization.
  storage.setItem(AUTHORIZATION_KEY, JSON.stringify({ version: 1, state, verifier, returnTarget, custodyId }));
  const challenge = base64url(new Uint8Array(await cryptoApi.subtle.digest("SHA-256", new TextEncoder().encode(verifier))));
  return { state, challenge };
}

export function readPortalAuthorization(storage: TabStorage): PortalAuthorization | null {
  const raw = storage.getItem(AUTHORIZATION_KEY);
  const value: unknown = raw ? JSON.parse(raw) : null;
  if (!isRecord(value) || value.version !== 1 || typeof value.state !== "string" ||
    !/^[A-Za-z0-9_-]{43}$/.test(value.state) || typeof value.verifier !== "string" ||
    !/^[A-Za-z0-9_-]{43}$/.test(value.verifier) || typeof value.returnTarget !== "string" ||
    typeof value.custodyId !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(value.custodyId)) return null;
  return { state: value.state, verifier: value.verifier, returnTarget: value.returnTarget, custodyId: value.custodyId };
}

export function consumePortalCallback(storage: TabStorage, fragment: string): { code: string; authorization: PortalAuthorization } | null {
  const params = new URLSearchParams(fragment.replace(/^#/, ""));
  const authorization = readPortalAuthorization(storage);
  if (!authorization || params.getAll("state").length !== 1 || params.getAll("code").length !== 1 ||
    params.get("state") !== authorization.state || !/^[A-Za-z0-9_-]{43}$/.test(params.get("code") ?? "")) return null;
  // One callback attempt only. A lost exchange starts a new authorization, retaining paid recovery.
  storage.removeItem(AUTHORIZATION_KEY);
  return { code: params.get("code")!, authorization };
}
