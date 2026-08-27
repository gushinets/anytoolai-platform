import { defineContentScript } from "wxt/utils/define-content-script";
import { captureInput } from "../content/captureInput";
import { detectSurface } from "../content/detectSurface";
import { CAPTURE_INPUT_MESSAGE, type CaptureInputResponse } from "../content/messages";

export default defineContentScript({
  matches: ["<all_urls>"],
  main() {
    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message !== CAPTURE_INPUT_MESSAGE) {
        return undefined;
      }
      const response: CaptureInputResponse = { ...captureInput(), surface: detectSurface() };
      sendResponse(response);
      return undefined;
    });
  },
});
