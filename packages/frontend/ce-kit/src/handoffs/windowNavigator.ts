import type { Navigate } from "./navigation";

/** Plain-browser/web-mirror `Navigate` adapter, backed by `window.open` (or a structural subset of it). */
export function createWindowNavigator(win: { open(url: string): unknown }): Navigate {
  return (url) => {
    win.open(url);
  };
}
