import { useEffect, useState } from "react";
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

/**
 * The already-queued session (an accepted handoff) a product page should attach to. The id comes
 * from `?session=` once, is removed from the address bar (so a bookmark or shared link does not
 * carry it), and is kept in this tab's `sessionStorage` so a reload still shows the result the
 * accept already charged for. `endAttach()` drops it once the user starts their own work.
 */
export function useAttachSession(productId: string, fromUrl: string | undefined) {
  const [attachSessionId] = useState(() => fromUrl ?? readStored(productId));
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
  return { attachSessionId, endAttach: () => writeStored(productId, null) };
}
