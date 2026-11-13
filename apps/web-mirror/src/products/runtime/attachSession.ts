import { useCallback, useRef, useState } from "react";
import { ATTACH_SESSION_PARAM } from "../../lib/hostUrls";
import { readProductDraft } from "./draftStorage";

const storageKey = (productId: string) => `anytoolai.attach_session.${productId}`;

/** One recovery selection per product per tab. `id` is the NEWEST accepted attachment this tab has seen for the
 * product and `rank` its order (see `rememberAttachSession`): a timestamp in MICROseconds, compared as a number
 * (as strings, "...:00Z" would sort after "...:00.5Z", which is later); a session that arrived without one (a
 * `?session=` link) has the lowest rank, 0. `active` is the session the person explicitly opened
 * (`chooseAttachSession`), whatever its order, the newest included: a visit restores it until it ends, then
 * `id` (if that is another, newer paid-for session). A valid `draft` selects an accepted own run instead;
 * attachments remain fallbacks until that saved run is cleared or an attachment is explicitly opened. */
type StoredAttach = {
  id?: string;
  rank: number;
  active?: string;
  draft?: { key: string; scenarioSessionId: string };
};

/**
 * An ISO timestamp as a rank in microseconds; anything unparseable ranks lowest. The backend stamps
 * `expires_at` with Python's microsecond-precision clock, so two handoffs can differ only below a
 * millisecond, and `Date.parse` drops everything past milliseconds: the digits it drops (the fraction's 4th to
 * 6th) are added back. (ms * 1000 + 999 stays far below Number.MAX_SAFE_INTEGER for any current date.)
 */
function toRank(timestamp: string): number {
  const ms = Date.parse(timestamp);
  if (Number.isNaN(ms)) {
    return 0;
  }
  const fraction = /\.(\d+)/.exec(timestamp)?.[1] ?? "";
  const microsPastMillisecond = Number(fraction.padEnd(6, "0").slice(3, 6));
  return ms * 1000 + microsPastMillisecond;
}

function readEntry(productId: string): StoredAttach | undefined {
  try {
    const raw = window.sessionStorage.getItem(storageKey(productId));
    if (raw === null) {
      return undefined;
    }
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) {
      return undefined;
    }
    const { id, rank, active, draft } = parsed as { id?: unknown; rank?: unknown; active?: unknown; draft?: unknown };
    let ownRun: StoredAttach["draft"];
    if (typeof draft === "object" && draft !== null) {
      const value = draft as { key?: unknown; scenarioSessionId?: unknown };
      if (typeof value.key === "string" && value.key.startsWith(`anytoolai.product_draft.${productId}.`) &&
        typeof value.scenarioSessionId === "string" && value.scenarioSessionId.length > 0) {
        ownRun = { key: value.key, scenarioSessionId: value.scenarioSessionId };
      }
    }
    if (typeof id !== "string" && ownRun === undefined) return undefined;
    return {
      id: typeof id === "string" ? id : undefined,
      rank: typeof rank === "number" ? rank : 0,
      active: typeof active === "string" ? active : undefined,
      draft: ownRun,
    };
  } catch {
    return undefined;
  }
}

function writeEntry(productId: string, entry: StoredAttach | null): boolean {
  try {
    if (entry === null || (entry.id === undefined && entry.active === undefined && entry.draft === undefined)) {
      window.sessionStorage.removeItem(storageKey(productId));
    } else {
      window.sessionStorage.setItem(storageKey(productId), JSON.stringify(entry));
    }
    return true;
  } catch {
    // Storage unavailable: the id then simply does not survive a reload.
    return false;
  }
}

/** The attachment to restore; undefined while a saved own run has recovery priority. */
export function readAttachSessionId(productId: string): string | undefined {
  const entry = readEntry(productId);
  if (entry?.draft && readProductDraft(entry.draft.key)?.run?.scenarioSessionId === entry.draft.scenarioSessionId) {
    return undefined;
  }
  return entry?.active ?? entry?.id;
}

/** Whether this session was explicitly opened, rather than retained by a late callback. */
export function isChosenAttachSession(productId: string, sessionId: string): boolean {
  return readEntry(productId)?.active === sessionId;
}

/** Select only a persisted own run; keep other accepted attachments as fallbacks. */
export function preferSavedOwnRun(productId: string, key: string, scenarioSessionId: string): boolean {
  if (readProductDraft(key)?.run?.scenarioSessionId !== scenarioSessionId) return false;
  const current = readEntry(productId);
  return writeEntry(productId, { ...current, rank: current?.rank ?? 0, draft: { key, scenarioSessionId } });
}

/**
 * Remembers a session an accepted handoff queued for `productId` when its Accept settled AFTER the person left
 * the consent page, so the product restores it on its next visit. Ordering-aware: the rank is the handoff's own
 * `expiresAt` (it grows with the handoff's creation time), and the remembered newest session is replaced only
 * by a NEWER one, so an older Accept whose response arrives late cannot overwrite the newer accepted session
 * the person is already on. A session the person explicitly opened (`chooseAttachSession`) stays what a visit
 * restores either way; a newer one only becomes the fallback behind it.
 */
export function rememberAttachSession(productId: string, scenarioSessionId: string, timestamp: string): void {
  const rank = toRank(timestamp);
  const current = readEntry(productId);
  if (current?.id === undefined || rank > current.rank) {
    writeEntry(productId, { id: scenarioSessionId, rank, ...selectionOf(current) });
  }
}

/**
 * The person opens this accepted handoff's session now (the Accept they just clicked, or "Open result" on a
 * spent token): it is what the tab restores from here on, whatever its order, until it ends
 * (`useAttachSession`'s `onAttachEnd`). It also becomes the newest when it is newer than the remembered one;
 * either way a newer Accept that settles late only becomes the fallback behind it, never the restored one.
 */
export function chooseAttachSession(productId: string, scenarioSessionId: string, timestamp: string): boolean {
  const rank = toRank(timestamp);
  const current = readEntry(productId);
  const newest = current?.id === undefined || rank > current.rank ? { id: scenarioSessionId, rank } : { id: current.id, rank: current.rank };
  return writeEntry(productId, { ...newest, active: scenarioSessionId }) &&
    readEntry(productId)?.active === scenarioSessionId;
}

/** A background Accept cannot replace the person's attached or own selection. */
function selectionOf(current: StoredAttach | undefined): Pick<StoredAttach, "active" | "draft"> {
  return { active: current?.active, draft: current?.draft };
}

/** Remove only this reference; another explicitly opened or later accepted session survives. */
export function forgetAttachSession(productId: string, id: string): void {
  const current = readEntry(productId);
  if (current?.active === id) {
    writeEntry(productId, { ...current, active: undefined, ...(current.id === id ? { id: undefined, rank: 0 } : {}) });
  } else if (current?.id === id) {
    // The rank belonged to the discarded id, not to the surviving active session.
    writeEntry(productId, { ...current, id: current.active, rank: 0 });
  }
}

/** A new explicit form/start leaves the previous result choice, retaining background fallbacks. */
export function forgetChosenAttachSession(productId: string): void {
  const id = readEntry(productId)?.active;
  if (id !== undefined) forgetAttachSession(productId, id);
}

/** What a product page needs to show an already-queued session, threaded route -> shell -> product ->
 * `ProductRunPage`. The route's `useAttachSession` is the one owner of the state behind it. */
export type AttachProps = {
  /** This visit explicitly selected a session, rather than restoring an older remembered handoff. */
  attachFromUrl?: boolean;
  /** Explicit scenario of a result deep link; the product selects its own matching mode. */
  attachScenarioId?: string;
  /**
   * The queued session to show (an accepted handoff's target); undefined for an ordinary visit. The page
   * polls it and renders its result with no start request and no quota charge (the accept already charged
   * it); there is no local input, so the form stays empty and no "previous details" notice shows. A definite
   * 404, a failed/expired session, or a result of another scenario or schema version ends in the run-failed
   * state (and ends the attach); an ambiguous failure keeps it locked and "Try again" polls the same session.
   */
  attachSessionId?: string;
  /** The server verified this session and its product scenario; persist before consuming its URL. */
  onAttachResolved?: (sessionId: string) => void;
  /** The page started polling the session (it is now on its way to the screen). */
  onAttachBegin?: (sessionId?: string) => void;
  /** The person moved on: "New task", a persisted own start, a replacement result, a mode switch,
   * or terminal failure. Safe to call at any time; it only acts after the attach began. */
  onAttachEnd?: (sessionId?: string) => void;
  /** Explicitly discard an unavailable attachment before runtime boot; never starts or cancels a run. */
  onAttachDiscard?: (sessionId?: string) => void;
};

/**
 * The route-level owner of an attached session. The id comes from `?session=` once, is removed from the
 * address bar after verification and persistence, and is kept in this tab's `sessionStorage`
 * so a reload still shows the result the accept already charged for. Normal `onAttachEnd` acts
 * only once `onAttachBegin` said the page really started showing it, and only if the
 * stored id is still the one it attached: a failed boot, or
 * the person typing in another mode, forgets nothing, so a reload still retries the paid-for session.
 * Explicit discard of an unavailable attachment also works before boot, without losing other sessions.
 */
export function useAttachSession(productId: string, fromUrl: string | undefined): AttachProps {
  const [attachSessionId, setAttachSessionId] = useState(() => fromUrl || readAttachSessionId(productId));
  const [attachFromUrl] = useState(() => Boolean(fromUrl));
  // The id this route attached, once the page started showing it. `onAttachEnd` forgets only that one: a late
  // Accept may have stored another session for the product meanwhile (`rememberAttachSession`).
  const begunIdRef = useRef<string | undefined>(undefined);
  const consumeUrl = useCallback((sessionId: string) => {
    const url = new URL(window.location.href);
    if (url.searchParams.get(ATTACH_SESSION_PARAM) !== sessionId) return;
    url.searchParams.delete(ATTACH_SESSION_PARAM);
    url.searchParams.delete("scenario");
    // `null` state: Next then copies its own history internals into it and syncs `useSearchParams`;
    // passing `history.state` (which carries Next's `__NA` marker) would make it skip that sync.
    window.history.replaceState(null, "", url);
  }, []);
  const onAttachResolved = useCallback((sessionId: string) => {
    if (sessionId !== fromUrl) return;
    // Keep the URL as the reload handle when storage refuses the confirmed choice.
    if (chooseAttachSession(productId, sessionId, "")) consumeUrl(sessionId);
  }, [productId, fromUrl, consumeUrl]);
  const onAttachBegin = useCallback((sessionId = attachSessionId) => {
    begunIdRef.current = sessionId;
  }, [attachSessionId]);
  const onAttachEnd = useCallback((sessionId?: string) => {
    const begunId = begunIdRef.current;
    const endedId = sessionId ?? begunId;
    if (begunId === endedId) begunIdRef.current = undefined;
    if (endedId !== undefined) {
      if (begunId === endedId) forgetAttachSession(productId, endedId);
      consumeUrl(endedId);
    }
  }, [productId, consumeUrl]);
  const onAttachDiscard = useCallback((sessionId = attachSessionId) => {
    if (sessionId === undefined) return;
    forgetAttachSession(productId, sessionId);
    consumeUrl(sessionId);
    if (begunIdRef.current === sessionId) begunIdRef.current = undefined;
    setAttachSessionId((current) => current === sessionId ? undefined : current);
  }, [productId, attachSessionId, consumeUrl]);
  return { attachSessionId, attachFromUrl, onAttachResolved, onAttachBegin, onAttachEnd, onAttachDiscard };
}
