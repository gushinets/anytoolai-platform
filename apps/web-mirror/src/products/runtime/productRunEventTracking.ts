import { generateIdempotencyKey, getOrCreateWebSessionId, trackClientEvent, type AsyncStorage, type PlatformApiClient, type WebClientEventType } from "@anytoolai/ce-kit";
import { assertNever, type ProductRunEvent } from "./productDefinition";

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

/**
 * `web.result_viewed` is one activation per session: a reload of a restored result (see
 * `useAttachSession`) renders it again, and must not count again. The tab (`sessionStorage`) keeps, per
 * session, the event id, the web session id it was sent under, and whether the backend accepted the event:
 * - accepted: nothing is sent again;
 * - not accepted (a lost response, a timeout, a rejection): the next report sends the SAME event id AND the
 *   same web session id, so a first attempt that the backend did commit is deduped there instead of
 *   creating a second row. The backend compares the whole event (the web session id is part of it) for a
 *   reused event id, so a retry under a different web session id (a reload without a usable `localStorage`
 *   mints a new one) would be rejected as `client_event_id_conflict`.
 * An unusable storage just falls back to reporting with a fresh id.
 */
type ResultViewedMark = { eventId: string; webSessionId?: string; accepted: boolean };

const resultViewedKey = (scenarioSessionId: string) => `anytoolai.result_viewed.${scenarioSessionId}`;

/** Sessions whose report is on the wire right now: a second event in the same tick sends nothing. */
const resultViewedInFlight = new Set<string>();

function readResultViewedMark(scenarioSessionId: string): ResultViewedMark | null {
  try {
    const raw = window.sessionStorage.getItem(resultViewedKey(scenarioSessionId));
    const parsed: unknown = raw === null ? null : JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null || typeof (parsed as ResultViewedMark).eventId !== "string") {
      return null;
    }
    const { eventId, webSessionId, accepted } = parsed as ResultViewedMark;
    return { eventId, webSessionId: typeof webSessionId === "string" ? webSessionId : undefined, accepted: accepted === true };
  } catch {
    return null;
  }
}

function writeResultViewedMark(scenarioSessionId: string, mark: ResultViewedMark): void {
  try {
    window.sessionStorage.setItem(resultViewedKey(scenarioSessionId), JSON.stringify(mark));
  } catch {
    // Storage unavailable: the report still goes out, it just cannot be deduped across a reload.
  }
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
 * `guestId` comes straight off every event (see `ProductRunEvent`'s own docstring): forwarding
 * `ProductRunPage`'s own single resolved value, rather than this module resolving its own, is what
 * guarantees every event -- `product_viewed` included -- agrees with whatever guest id actually
 * ran the scenario, with no second, independently-resolved identity anywhere in this module to
 * diverge from it.
 *
 * Never blocks the UI: `trackClientEvent` reports failure as `{ ok: false }` instead of throwing,
 * and this only ever fires from a UI event handler with nothing for the caller to await. The
 * trailing `.catch()` is a backstop, not a expected path -- every promise in the chain above it is
 * already documented as never rejecting, but a fire-and-forget chain like this one bypasses
 * `emitEvent()`'s own defensive wrapper (the handler itself returns `void`, not the chain), so a
 * future regression of any of those "never rejects" guarantees would otherwise surface as an
 * unhandled promise rejection instead of being silently absorbed like everywhere else in this
 * event path.
 */
export function createProductRunEventTracker(
  client: PlatformApiClient,
  productId: string,
  storage: AsyncStorage,
): (event: ProductRunEvent) => void {
  return (event) => {
    const eventType = webEventTypeForRunEvent(event.type);
    // A completed run the product does not count as "viewed" (ProductDefinition.emitsResultViewed).
    if (eventType === undefined || (event.type === "scenario_completed" && !event.resultViewed)) {
      return;
    }
    const scenarioSessionId = "scenarioSessionId" in event ? event.scenarioSessionId : undefined;
    // Only `scenario_completed` is a once-per-session report; the others have no mark.
    const resultViewedSessionId = event.type === "scenario_completed" ? event.scenarioSessionId : undefined;
    let eventId: string | undefined;
    let sentWebSessionId: string | undefined;
    if (resultViewedSessionId !== undefined) {
      const mark = readResultViewedMark(resultViewedSessionId);
      if (mark?.accepted || resultViewedInFlight.has(resultViewedSessionId)) {
        return;
      }
      eventId = mark?.eventId ?? generateIdempotencyKey();
      sentWebSessionId = mark?.webSessionId;
      writeResultViewedMark(resultViewedSessionId, { eventId, webSessionId: sentWebSessionId, accepted: false });
      resultViewedInFlight.add(resultViewedSessionId);
    }

    void getOrCreateWebSessionId(storage)
      .then((currentWebSessionId) => {
        // A retry keeps the web session id of the first attempt (see the mark's docstring).
        const webSessionId = sentWebSessionId ?? currentWebSessionId;
        if (resultViewedSessionId !== undefined && eventId !== undefined) {
          writeResultViewedMark(resultViewedSessionId, { eventId, webSessionId, accepted: false });
        }
        return trackClientEvent(client, {
          eventType,
          productId,
          frontendId: FRONTEND_ID,
          webSessionId,
          guestId: event.guestId,
          scenarioSessionId,
          eventId,
        });
      })
      .then((result) => {
        // An id conflict means the backend already holds an event under our own id (minted per session): it
        // is recorded, just under other details (an older mark without a web session id), so it is done too.
        const recorded = result.ok || (result.error.type === "backend_error" && result.error.code === "client_event_id_conflict");
        if (resultViewedSessionId !== undefined && eventId !== undefined && recorded) {
          const stored = readResultViewedMark(resultViewedSessionId);
          writeResultViewedMark(resultViewedSessionId, { eventId, webSessionId: stored?.webSessionId, accepted: true });
        }
      })
      .catch(() => {
        // See this function's own docstring: backstop only, not an expected path.
      })
      .finally(() => {
        if (resultViewedSessionId !== undefined) {
          resultViewedInFlight.delete(resultViewedSessionId);
        }
      });
  };
}
