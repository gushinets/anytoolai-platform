import {
  createInMemoryAsyncStorage,
  createWindowLocalStorageAdapter,
  getOrCreateWebSessionId,
  trackClientEvent,
  type PlatformApiClient,
  type WebClientEventType,
} from "@anytoolai/ce-kit";
import type { ProductRunEvent } from "./productDefinition";

/** apps/web-mirror is deployed as exactly one backend frontend -- every product's own
 * `frontends.yaml` registers `web_mirror` as its (only) web frontend. */
const WEB_MIRROR_FRONTEND_ID = "web_mirror";

/**
 * Maps the shared runtime's own product-neutral funnel events to the backend's `web.*` client-
 * event allowlist (docs/architecture/event-taxonomy.md, ANY-17). `copy_activated` has no entry: a
 * successful copy already records `client.result_copied`/`client.next_action_clicked`
 * server-side via the `copy_result` next-action call itself
 * (`copyResultAndRecordActivation`/`ProductRunPage.handleCopy`) -- re-reporting it here would be
 * a duplicate, not a new signal.
 */
const WEB_EVENT_TYPE_BY_KIND: Partial<Record<ProductRunEvent["type"], WebClientEventType>> = {
  product_viewed: "web.product_viewed",
  form_started: "web.form_started",
  form_submitted: "web.form_submitted",
  scenario_completed: "web.result_viewed",
};

/**
 * Builds the `onEvent` handler a product page hands to `ProductRunPage`/its product component:
 * translates the shared runtime's funnel events into `POST /v1/client-events` calls, closing over
 * one device-local `web_session_id` for the tracker's lifetime (persisted across reloads the same
 * way guest identity is -- falls back to an in-memory id when `localStorage` is unavailable).
 *
 * Never throws and never blocks the product experience: delivery failure is swallowed, exactly
 * like every other CE-kit analytics call (the platform contract explicitly allows this metric to
 * undercount). This was ANY-453's own deliberately deferred gap ("ANY-17's job plus whichever
 * ticket composes it into the route") -- ANY-414 is that ticket, and wiring it here (not inside a
 * single product) is what makes it benefit every product sharing this route, not just one.
 */
export function createClientEventTracker(
  client: PlatformApiClient,
  productId: string,
): (event: ProductRunEvent) => void {
  const storage = createWindowLocalStorageAdapter() ?? createInMemoryAsyncStorage();
  let webSessionId: Promise<string> | null = null;

  return function trackProductRunEvent(event: ProductRunEvent): void {
    const eventType = WEB_EVENT_TYPE_BY_KIND[event.type];
    if (!eventType) {
      return;
    }
    webSessionId ??= getOrCreateWebSessionId(storage);
    void webSessionId
      .then((resolvedWebSessionId) =>
        trackClientEvent(client, {
          eventType,
          productId,
          frontendId: WEB_MIRROR_FRONTEND_ID,
          webSessionId: resolvedWebSessionId,
          scenarioSessionId: "scenarioSessionId" in event ? event.scenarioSessionId : undefined,
        }),
      )
      .catch(_noop);
  };
}

function _noop(): void {
  // Analytics delivery failure must never surface to the caller.
}
