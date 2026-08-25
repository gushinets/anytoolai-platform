import type { Navigate } from "./navigation";

/** Plain-browser/web-mirror `Navigate` adapter, backed by `window.open` (or a structural subset of it). */
export function createWindowNavigator(
  win: { open(url: string, target?: string, features?: string): unknown },
): Navigate {
  return (url) => {
    win.open(url, "_blank", "noopener");
  };
}
