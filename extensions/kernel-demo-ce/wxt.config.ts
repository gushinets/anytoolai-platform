import { defineConfig } from "wxt";
import { manifestConfig } from "./src/manifest.config";

export default defineConfig({
  srcDir: "src",
  // WXT's global auto-imports (e.g. a bare `storage` identifier -> `wxt/utils/storage`) apply to
  // every module Vite touches, including @anytoolai/ce-kit's own source (a workspace package, not
  // prebuilt) -- its regex-based scan isn't scope-aware, so any workspace dep with a same-named
  // local variable can break the build the same way one already did (see localStorageAdapter.ts).
  // Entrypoints import `defineBackground`/`defineContentScript` explicitly instead.
  imports: false,
  manifest: {
    ...manifestConfig,
    // Port isn't part of Chrome's match-pattern grammar, so these also match the
    // per-checkout dev-up API port (18000 + a repo-path-derived offset, see
    // scripts/agent/runner.py) -- host_permissions here is what lets sidepanel/background
    // fetch() calls bypass CORS against platform-api, unlike a content script's page fetch.
    host_permissions: ["http://localhost/*", "http://127.0.0.1/*"],
    permissions: ["sidePanel", "storage"],
  },
});
