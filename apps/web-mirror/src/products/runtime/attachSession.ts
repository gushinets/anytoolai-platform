import { useCallback, useEffect, useRef, useState } from "react";
import { ATTACH_SESSION_PARAM } from "../../lib/hostUrls";

const storageKey = (productId: string) => `anytoolai.attach_session.${productId}`;

/** One remembered session per product per tab. `rank` orders accepted handoffs (see `rememberAttachSession`):
 * a timestamp in milliseconds, compared as a NUMBER (as strings, "...:00Z" would sort after "...:00.5Z", which
 * is later). A session that arrived without one (a `?session=` link) has the lowest rank, 0. */
type StoredAttach = { id: string; rank: number };

/** An ISO timestamp as a rank; anything unparseable ranks lowest. */
function toRank(timestamp: string): number {
  const ms = Date.parse(timestamp);
  return Number.isNaN(ms) ? 0 : ms;
}

function readEntry(productId: string): StoredAttach | undefined {
  try {
    const raw = window.sessionStorage.getItem(storageKey(productId));
    if (raw === null) {
      return undefined;
    }
    const parsed: unknown = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null && typeof (parsed as StoredAttach).id === "string"
      ? { id: (parsed as StoredAttach).id, rank: typeof (parsed as StoredAttach).rank === "number" ? (parsed as StoredAttach).rank : 0 }
      : undefined;
  } catch {
    return undefined;
  }
}

function writeEntry(productId: string, entry: StoredAttach | null): void {
  try {
    if (entry === null) {
      window.sessionStorage.removeItem(storageKey(productId));
    } else {
      window.sessionStorage.setItem(storageKey(productId), JSON.stringify(entry));
    }
  } catch {
    // Storage unavailable: the id then simply does not survive a reload.
  }
}

/** The remembered session id for `productId`, if any (what a visit would restore). */
export function readAttachSessionId(productId: string): string | undefined {
  return readEntry(productId)?.id;
}

/**
 * Remembers a session an accepted handoff queued for `productId` (an Accept that settled after the person left
 * the consent page, or just before navigating), so the product restores it on its next visit. Ordering-aware:
 * the rank is the handoff's own `expiresAt` (it grows with the handoff's creation time), and a remembered
 * session is replaced only by a NEWER one, so an older Accept whose response arrives late cannot overwrite
 * the newer accepted session the person is already on.
 */
export function rememberAttachSession(productId: string, scenarioSessionId: string, timestamp: string): void {
  const rank = toRank(timestamp);
  const current = readEntry(productId);
  if (current === undefined || current.id === scenarioSessionId || rank > current.rank) {
    writeEntry(productId, { id: scenarioSessionId, rank: Math.max(rank, current?.rank ?? 0) });
  }
}

/** What a product page needs to show an already-queued session, threaded route -> shell -> product ->
 * `ProductRunPage`. The route's `useAttachSession` is the one owner of the state behind it. */
export type AttachProps = {
  /**
   * The queued session to show (an accepted handoff's target); undefined for an ordinary visit. The page
   * polls it and renders its result with no start request and no quota charge (the accept already charged
   * it); there is no local input, so the form stays empty and no "previous details" notice shows. A definite
   * 404, a failed/expired session, or a result of another scenario or schema version ends in the run-failed
   * state (and ends the attach); an ambiguous failure keeps it locked and "Try again" polls the same session.
   */
  attachSessionId?: string;
  /** The page started polling the session (it is now on its way to the screen). */
  onAttachBegin?: () => void;
  /** The person moved on from the attached session: "New task", own work replacing its result, a mode
   * switch, or its terminal failure. Safe to call at any time; it only acts after the attach began. */
  onAttachEnd?: () => void;
};

/**
 * The route-level owner of an attached session. The id comes from `?session=` once, is removed from the
 * address bar (so a bookmark or shared link does not carry it), and is kept in this tab's `sessionStorage`
 * so a reload still shows the result the accept already charged for. It is forgotten only by
 * `onAttachEnd`, only once `onAttachBegin` said the page really started showing it, and only if the
 * stored id is still the one it attached: a failed boot, or
 * the person typing in another mode, forgets nothing, so a reload still retries the paid-for session.
 */
export function useAttachSession(productId: string, fromUrl: string | undefined): AttachProps {
  const [attachSessionId] = useState(() => fromUrl || readEntry(productId)?.id);
  // The id this route attached, once the page started showing it. `onAttachEnd` forgets only that one: a late
  // Accept may have stored another session for the product meanwhile (`rememberAttachSession`).
  const begunIdRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!fromUrl) {
      return;
    }
    // A session the consent page already remembered keeps its rank; a bare link starts at the lowest.
    const current = readEntry(productId);
    writeEntry(productId, current?.id === fromUrl ? current : { id: fromUrl, rank: 0 });
    const url = new URL(window.location.href);
    url.searchParams.delete(ATTACH_SESSION_PARAM);
    // `null` state: Next then copies its own history internals into it and syncs `useSearchParams`;
    // passing `history.state` (which carries Next's `__NA` marker) would make it skip that sync.
    window.history.replaceState(null, "", url);
  }, [productId, fromUrl]);
  const onAttachBegin = useCallback(() => {
    begunIdRef.current = attachSessionId;
  }, [attachSessionId]);
  const onAttachEnd = useCallback(() => {
    const begunId = begunIdRef.current;
    begunIdRef.current = undefined;
    if (begunId !== undefined && readEntry(productId)?.id === begunId) {
      writeEntry(productId, null);
    }
  }, [productId]);
  return { attachSessionId, onAttachBegin, onAttachEnd };
}
