import { useCallback, useEffect, useRef, useState } from "react";
import { ATTACH_SESSION_PARAM } from "../../lib/hostUrls";

const storageKey = (productId: string) => `anytoolai.attach_session.${productId}`;

function readStored(productId: string): string | undefined {
  try {
    return window.sessionStorage.getItem(storageKey(productId)) ?? undefined;
  } catch {
    return undefined;
  }
}

function writeStored(productId: string, id: string | null): void {
  try {
    if (id === null) {
      window.sessionStorage.removeItem(storageKey(productId));
    } else {
      window.sessionStorage.setItem(storageKey(productId), id);
    }
  } catch {
    // Storage unavailable: the id then simply does not survive a reload.
  }
}

/** Remembers a session an accepted handoff queued for `productId` without navigating there (an Accept that
 * settled after the person left the consent page), so the product restores it on its next visit. */
export function rememberAttachSession(productId: string, scenarioSessionId: string): void {
  writeStored(productId, scenarioSessionId);
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
  const [attachSessionId] = useState(() => fromUrl || readStored(productId));
  // The id this route attached, once the page started showing it. `onAttachEnd` forgets only that one: a late
  // Accept may have stored another session for the product meanwhile (`rememberAttachSession`).
  const begunIdRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!fromUrl) {
      return;
    }
    writeStored(productId, fromUrl);
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
    if (begunId !== undefined && readStored(productId) === begunId) {
      writeStored(productId, null);
    }
  }, [productId]);
  return { attachSessionId, onAttachBegin, onAttachEnd };
}
