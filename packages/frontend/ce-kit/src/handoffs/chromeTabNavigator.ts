import type { Navigate } from "./navigation";

/**
 * Structural subset of `chrome.tabs`'s promise-based API that this adapter actually calls.
 * `chrome.tabs` itself satisfies this shape, so callers can pass it directly without CE-kit
 * depending on `@types/chrome` -- the same trick `ChromeStorageArea` uses.
 */
export type ChromeTabsArea = {
  create(props: { url: string }): Promise<unknown>;
};

/** Chrome-extension `Navigate` adapter, backed by `chrome.tabs.create`. */
export function createChromeTabNavigator(tabs: ChromeTabsArea): Navigate {
  return async (url) => {
    await tabs.create({ url });
  };
}
