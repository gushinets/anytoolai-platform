import {
  getOrCreateWebSessionId,
  trackClientEvent,
  type AsyncStorage,
  type PlatformApiClient,
  type WebClientEventType,
} from "@anytoolai/ce-kit";
import type { ProductRunEvent } from "./productDefinition";

const FRONTEND_ID = "web_mirror";

/**
 * Exhaustive over `ProductRunEvent["type"]` (docs/agent/coding-conventions.md's "Exhaustiveness"
 * rule, mirrored by `ProductRunPage.tsx`'s own `assertNever()` switch over `Phase["kind"]`): a
 * future new `ProductRunEvent` variant fails typecheck here instead of silently never reaching the
 * backend.
 */
function webEventTypeForRunEvent(eventType: ProductRunEvent["type"]): WebClientEventType | undefined {
  switch (eventType) {
    case "product_viewed":
      return "web.product_viewed";
    case "form_started":
      return "web.form_started";
    case "form_submitted":
      return "web.form_submitted";
    case "scenario_completed":
      return "web.result_viewed";
    case "copy_activated":
      // No web.* counterpart on purpose -- see this function's caller docstring below.
      return undefined;
    default:
      return assertNever(eventType);
  }
}

function assertNever(value: never): never {
  throw new Error(`Unhandled ProductRunEvent type: ${JSON.stringify(value)}`);
}

/**
 * Wires the shared runtime's injectable `ProductRunEvent` callback (ANY-453) to ANY-17's real
 * `POST /v1/client-events` ingestion. This lives in the composition layer (called from
 * `app/products/[productId]/page.tsx`), not inside `ProductRunPage`, so the shared runtime stays
 * untied to any transport and keeps importing no product module.
 *
 * `copy_activated` has no `web.*` counterpart on purpose: the backend already records
 * `next_action_clicked` when `copy_result` fires (`ProductRunPage`'s own `nextAction()` call), so
 * tracking it again here would double-count the same activation under a second event type.
 *
 * `guestId` comes straight off the event for every variant but `product_viewed` (see
 * `ProductRunEvent`'s own docstring for why: forwarding `ProductRunPage`'s own resolved value
 * avoids a second, independent resolution that can diverge from it in a private-browsing/
 * storage-unavailable fallback). Only `product_viewed` -- fired before that resolution has
 * necessarily settled -- still resolves its own via `client.createGuestIdentity()`; the live
 * backend requires at least one of guest_id/user_id/scenario_session_id per event, and this is the
 * only variant with neither a carried `guestId` nor a `scenarioSessionId`.
 *
 * Never blocks the UI: `trackClientEvent`/`createGuestIdentity` report failure as `{ ok: false }`
 * instead of throwing, and this only ever fires from a UI event handler with nothing for the
 * caller to await.
 */
export function createProductRunEventTracker(
  client: PlatformApiClient,
  productId: string,
  storage: AsyncStorage,
): (event: ProductRunEvent) => void {
  return (event) => {
    const eventType = webEventTypeForRunEvent(event.type);
    if (eventType === undefined) {
      return;
    }
    const scenarioSessionId = "scenarioSessionId" in event ? event.scenarioSessionId : undefined;
    const guestIdPromise: Promise<string | undefined> =
      "guestId" in event
        ? Promise.resolve(event.guestId)
        : client.createGuestIdentity({ storage }).then((result) => (result.ok ? result.value.guestId : undefined));

    void Promise.all([getOrCreateWebSessionId(storage), guestIdPromise]).then(([webSessionId, guestId]) =>
      trackClientEvent(client, {
        eventType,
        productId,
        frontendId: FRONTEND_ID,
        webSessionId,
        guestId,
        scenarioSessionId,
      }),
    );
  };
}
