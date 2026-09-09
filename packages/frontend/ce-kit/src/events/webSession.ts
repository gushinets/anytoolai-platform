import { isRecord } from "../api/parsing";
import { generateIdempotencyKey } from "../scenarios/idempotencyKey";
import type { AsyncStorage } from "../storage/asyncStorage";

export const DEFAULT_WEB_SESSION_STORAGE_KEY = "anytoolai.web_session";
/** Design: docs/superpowers/specs/2026-09-03-web-first-product-framework-design.md. */
export const WEB_SESSION_INACTIVITY_TIMEOUT_MS = 30 * 60 * 1000;

export type WebSessionOptions = {
  storageKey?: string;
};

type StoredWebSession = {
  id: string;
  lastActivityAt: number;
};

/**
 * Single-flight guard per (backingStorage, storageKey) pair -- without it, two calls that both
 * start before either finishes its `get()` would each see "no active session" and mint their own
 * id, with the later `set()` silently winning and splitting that request's events across two
 * `web_session_id` values. Keyed by the storage instance itself (not a global), so unrelated
 * `AsyncStorage` instances never contend, and entries can be garbage-collected with their storage.
 */
const inFlightCalls = new WeakMap<AsyncStorage, Map<string, Promise<string>>>();

/**
 * Returns the current device-local `web_session_id`, minting a new one if none is stored or if
 * more than 30 minutes have passed since the last call touched it. Every call -- a reuse or a
 * rotation -- refreshes `lastActivityAt`, so the session extends as long as calls keep arriving
 * within the inactivity window; it only rotates once a gap exceeds that window (including a gap
 * measured as negative by a backward system-clock jump, which is treated as inactive rather than
 * "trivially still active forever"). A storage failure never throws: it falls back to a fresh id
 * for this call, matching `refreshGuestIdentity()`'s "storage can't be trusted" handling elsewhere
 * in CE-kit.
 *
 * Parameter named `backingStorage`, not `storage` -- see `createLocalStorageAdapter()`'s docstring
 * for why a bare `storage` identifier can't be used in a ce-kit source file bundled directly into
 * a Chrome-extension (WXT) build.
 */
export async function getOrCreateWebSessionId(
  backingStorage: AsyncStorage,
  options?: WebSessionOptions,
): Promise<string> {
  const storageKey = options?.storageKey ?? DEFAULT_WEB_SESSION_STORAGE_KEY;

  let callsForStorage = inFlightCalls.get(backingStorage);
  if (callsForStorage === undefined) {
    callsForStorage = new Map();
    inFlightCalls.set(backingStorage, callsForStorage);
  }
  const inFlight = callsForStorage.get(storageKey);
  if (inFlight !== undefined) {
    return inFlight;
  }

  const calls = callsForStorage;
  const call = resolveWebSessionId(backingStorage, storageKey).finally(() => {
    calls.delete(storageKey);
  });
  callsForStorage.set(storageKey, call);
  return call;
}

async function resolveWebSessionId(backingStorage: AsyncStorage, storageKey: string): Promise<string> {
  const now = Date.now();

  let stored: StoredWebSession | null;
  try {
    const raw = await backingStorage.get(storageKey);
    stored = raw === undefined ? null : parseStoredWebSession(raw);
  } catch {
    stored = null;
  }

  const id = isWithinInactivityWindow(stored, now) ? stored.id : generateIdempotencyKey();

  try {
    const next: StoredWebSession = { id, lastActivityAt: now };
    await backingStorage.set(storageKey, JSON.stringify(next));
  } catch {
    // Best-effort persistence -- the id returned for this call is still correct even if a later
    // call can't find it and mints another.
  }

  return id;
}

function isWithinInactivityWindow(
  stored: StoredWebSession | null,
  now: number,
): stored is StoredWebSession {
  if (stored === null) {
    return false;
  }
  const elapsed = now - stored.lastActivityAt;
  return elapsed >= 0 && elapsed <= WEB_SESSION_INACTIVITY_TIMEOUT_MS;
}

function parseStoredWebSession(raw: string): StoredWebSession | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(parsed) || typeof parsed.id !== "string" || typeof parsed.lastActivityAt !== "number") {
    return null;
  }
  return { id: parsed.id, lastActivityAt: parsed.lastActivityAt };
}
