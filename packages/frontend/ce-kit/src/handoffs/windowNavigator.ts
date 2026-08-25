import type { Navigate } from "./navigation";

/**
 * Plain-browser/web-mirror `Navigate` adapter, backed by same-tab `location.assign` (or a
 * structural subset of it). Same-tab redirect, not `window.open`, because `openHandoffConsent()`
 * is documented to run after `await createHandoff()` -- by then the click's transient user
 * activation is gone, so a new-tab/popup call is liable to be silently blocked.
 */
export function createWindowNavigator(win: { location: { assign(url: string): unknown } }): Navigate {
  return (url) => {
    win.location.assign(url);
  };
}
