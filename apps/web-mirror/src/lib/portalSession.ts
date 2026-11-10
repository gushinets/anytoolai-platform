import {
  PORTAL_SESSION_KEY, generateIdempotencyKey, parsePortalOwner, readPortalSession, samePortalOwner, writePortalSession,
  type PaidStartPersistence, type PlatformApiClient, type PortalOwner, type PortalSession, type TabStorage,
} from "@anytoolai/ce-kit";

const MODE_KEY = "anytoolai.portal_mode.v1";
export const tabStorage: TabStorage = {
  getItem: (key) => window.sessionStorage.getItem(key),
  setItem: (key, value) => window.sessionStorage.setItem(key, value),
  removeItem: (key) => window.sessionStorage.removeItem(key),
};
type IdentityState = { generation: number; custodyId: string | null } & (
  | { kind: "guest" }
  | { kind: "required"; owner: PortalOwner | null }
  | { kind: "authorized"; session: PortalSession }
);
let state: IdentityState | undefined;
const listeners = new Set<() => void>();

export function getPortalIdentity(): IdentityState {
  state ??= readStoredIdentity(0);
  return state;
}

function readStoredIdentity(generation: number): IdentityState {
  try {
    const session = readPortalSession(tabStorage);
    const mode = tabStorage.getItem(MODE_KEY);
    const saved: unknown = mode ? JSON.parse(mode) : null;
    const owner = typeof saved === "object" && saved !== null && "owner" in saved ? parsePortalOwner(saved.owner) : null;
    const custodyId = typeof saved === "object" && saved !== null && "version" in saved && saved.version === 1 &&
      "custodyId" in saved && typeof saved.custodyId === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(saved.custodyId) ? saved.custodyId : null;
    // Legacy custody without an epoch requires reauthorization, retaining its owner-bound recovery.
    return session && custodyId && owner && samePortalOwner(owner, session.owner) ? { kind: "authorized", session, generation, custodyId }
      : mode || session ? { kind: "required", owner: mode ? owner : session?.owner ?? null, generation, custodyId }
        : { kind: "guest", generation, custodyId };
  } catch {
    // An unreadable paid tab cannot become an anonymous execution implicitly.
    return { kind: "required", owner: null, generation, custodyId: null };
  }
}

function sameIdentity(left: IdentityState, right: IdentityState): boolean {
  if (left.custodyId !== right.custodyId) return false;
  if (left.kind === "authorized" && right.kind === "authorized") {
    return left.session.accessToken === right.session.accessToken &&
      left.session.expiresAt === right.session.expiresAt && samePortalOwner(left.session.owner, right.session.owner);
  }
  if (left.kind === "required" && right.kind === "required") {
    return left.owner === right.owner || (left.owner !== null && right.owner !== null && samePortalOwner(left.owner, right.owner));
  }
  return left.kind === "guest" && right.kind === "guest";
}

/** BFCache retains this module's memory while another document in the tab can change custody. */
export function synchronizePortalIdentity(): IdentityState {
  const current = getPortalIdentity();
  let stored = readStoredIdentity(current.generation + 1);
  if (current.kind !== "guest" && stored.kind === "guest") {
    stored = { kind: "required", owner: null, generation: stored.generation, custodyId: stored.custodyId };
  }
  if (!sameIdentity(current, stored)) publish(stored);
  const latest = getPortalIdentity();
  if (latest.kind === "authorized" && Date.parse(latest.session.expiresAt) <= Date.now()) requirePortalAuthorization();
  return getPortalIdentity();
}

function publish(next: IdentityState): void {
  state = next;
  for (const listener of listeners) listener();
}

export function subscribePortalIdentity(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function clearPaidPrivateState(): void {
  // Only this feature's tab data; guest identity and unrelated storage are preserved.
  const keys = Object.keys(window.sessionStorage).filter((key) =>
    ["anytoolai.paid_start.", "anytoolai.attach_session.", "anytoolai.result_viewed."].some((prefix) => key.startsWith(prefix)));
  for (const key of keys) tabStorage.removeItem(key);
}

function writeCustody(owner: PortalOwner | null, custodyId: string): void {
  const raw = JSON.stringify({ version: 1, owner, custodyId });
  tabStorage.setItem(MODE_KEY, raw);
  if (tabStorage.getItem(MODE_KEY) !== raw) throw new Error("portal_storage_unavailable");
}

export function requirePortalAuthorization(clearPrivate = false): boolean {
  const current = getPortalIdentity();
  const owner = current.kind === "authorized" ? current.session.owner : current.kind === "required" ? current.owner : null;
  // Publish first: even a storage failure must invalidate all previous clients and displayed state.
  const custodyId = generateIdempotencyKey();
  const nextOwner = clearPrivate ? null : owner;
  publish({ kind: "required", owner: nextOwner, generation: current.generation + 1, custodyId });
  try {
    tabStorage.removeItem(PORTAL_SESSION_KEY);
    if (clearPrivate) clearPaidPrivateState();
  } catch {
    // Fail closed in memory if the browser refuses removal as well as writes.
  }
  try {
    writeCustody(nextOwner, custodyId);
    return true;
  } catch {
    // Removing an old epoch prevents it from surviving a refused logout write.
    try { tabStorage.removeItem(MODE_KEY); } catch { /* Storage denial still fails closed in memory. */ }
    return false;
  }
}

export function installPortalSession(session: PortalSession): void {
  const current = getPortalIdentity();
  const previous = current.kind === "authorized" ? current.session.owner : current.kind === "required" ? current.owner : null;
  if (!previous || !samePortalOwner(previous, session.owner)) clearPaidPrivateState();
  if (Date.parse(session.expiresAt) <= Date.now()) throw new Error("portal_session_expired");
  const custodyId = generateIdempotencyKey();
  try {
    tabStorage.removeItem(PORTAL_SESSION_KEY);
    writeCustody(session.owner, custodyId);
    writePortalSession(tabStorage, session);
    const stored = readPortalSession(tabStorage);
    if (!stored || stored.accessToken !== session.accessToken || stored.expiresAt !== session.expiresAt || !samePortalOwner(stored.owner, session.owner)) throw new Error("portal_storage_unavailable");
  } catch (error) {
    requirePortalAuthorization();
    throw error;
  }
  publish({ kind: "authorized", session, generation: current.generation + 1, custodyId });
}

export function isPortalGenerationCurrent(generation: number): boolean {
  const current = synchronizePortalIdentity();
  return current.generation === generation && current.kind === "authorized";
}

export function getPaidPersistence(client: PlatformApiClient): PaidStartPersistence | undefined {
  return client.portalIdentity ? { storage: tabStorage, owner: client.portalIdentity.owner, isCurrent: client.portalIdentity.isCurrent } : undefined;
}
