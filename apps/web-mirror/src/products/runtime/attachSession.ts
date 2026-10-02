import { useCallback, useEffect, useRef, useState } from "react";
import { ATTACH_SESSION_PARAM } from "../../lib/hostUrls";

const storageKey = (productId: string) => `anytoolai.attach_session.${productId}`;

/** One remembered entry per product per tab. `id` is what a visit restores. `rank` is the order of the NEWEST
 * accepted handoff this tab has seen for the product (see `rememberAttachSession`), a timestamp in MICROseconds,
 * compared as a number (as strings, "...:00Z" would sort after "...:00.5Z", which is later); a session that
 * arrived without one (a `?session=` link) has the lowest rank, 0. `newestId` names that newest session when
 * the person explicitly opened an older one (`id`): the paid-for newer one is kept as the fallback and
 * restored once the opened one ends. Absent, `id` itself is the newest. */
type StoredAttach = { id: string; rank: number; newestId?: string };

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
    if (typeof parsed !== "object" || parsed === null || typeof (parsed as StoredAttach).id !== "string") {
      return undefined;
    }
    const { id, rank, newestId } = parsed as StoredAttach;
    return { id, rank: typeof rank === "number" ? rank : 0, ...(typeof newestId === "string" ? { newestId } : {}) };
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
 * Remembers a session an accepted handoff queued for `productId` when its Accept settled AFTER the person left
 * the consent page, so the product restores it on its next visit. Ordering-aware: the rank is the handoff's own
 * `expiresAt` (it grows with the handoff's creation time), and a remembered session is replaced only by a NEWER
 * one, so an older Accept whose response arrives late cannot overwrite the newer accepted session the person is
 * already on. Use `chooseAttachSession` for a session the person opens themselves.
 */
export function rememberAttachSession(productId: string, scenarioSessionId: string, timestamp: string): void {
  keepEntry(productId, scenarioSessionId, timestamp, false);
}

/**
 * The person opens this accepted handoff's session now (the Accept they just clicked, or "Open result" on a
 * spent token): it is what the tab restores from here on, whatever its order; a newer remembered one is
 * replaced too. The newest order seen stays as the rank, so a late older Accept still cannot replace it.
 */
export function chooseAttachSession(productId: string, scenarioSessionId: string, timestamp: string): void {
  keepEntry(productId, scenarioSessionId, timestamp, true);
}

function keepEntry(productId: string, scenarioSessionId: string, timestamp: string, chosen: boolean): void {
  const rank = toRank(timestamp);
  const current = readEntry(productId);
  const isNewest = current === undefined || rank > current.rank;
  if (!chosen) {
    if (isNewest || current.id === scenarioSessionId) {
      writeEntry(productId, { id: scenarioSessionId, rank: Math.max(rank, current?.rank ?? 0), ...(isNewest ? {} : keptNewest(current)) });
    }
    return;
  }
  // Chosen: it is what is restored; the newest session (this one, or the remembered one it is older than) stays
  // as the fallback.
  const newestId = isNewest ? scenarioSessionId : (current.newestId ?? current.id);
  writeEntry(productId, { id: scenarioSessionId, rank: Math.max(rank, current?.rank ?? 0), ...(newestId === scenarioSessionId ? {} : { newestId }) });
}

function keptNewest(current: StoredAttach): { newestId?: string } {
  return current.newestId === undefined ? {} : { newestId: current.newestId };
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
    // A bare link has no order of its own (rank 0): it keeps the rank of the same session the consent page
    // remembered, and never replaces a different session that has one (a newer accepted handoff).
    const current = readEntry(productId);
    if (current === undefined || current.rank === 0) {
      writeEntry(productId, { id: fromUrl, rank: 0 });
    }
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
    const current = readEntry(productId);
    if (begunId !== undefined && current?.id === begunId) {
      // The opened session ended: the newer accepted one it displaced (if any) is what a visit restores now.
      writeEntry(productId, current.newestId === undefined ? null : { id: current.newestId, rank: current.rank });
    }
  }, [productId]);
  return { attachSessionId, onAttachBegin, onAttachEnd };
}
