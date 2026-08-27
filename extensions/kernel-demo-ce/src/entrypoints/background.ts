import { defineBackground } from "wxt/utils/define-background";

export default defineBackground(() => {
  // MV3 sidepanel: without this, the toolbar icon click does nothing (the panel API defaults to
  // requiring an explicit chrome.sidePanel.open() call per tab).
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {
    // Not fatal -- the user can still be routed to the panel through other UI later.
  });
});
