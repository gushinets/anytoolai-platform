"use client";

import { useState } from "react";
import { GeneratedTextRenderer } from "@anytoolai/web-result-kit";

export type ResultViewProps = {
  text: string;
  /** Called once the clipboard write itself succeeds. Which (if any) next action to fire after a
   * copy is product-specific, so it stays out of this shared component. */
  onCopied?: () => void;
};

/** Canonical text result plus a copy-to-clipboard button. The result stays visible and copyable
 * even if `onCopied` (or whatever it triggers) fails -- only the clipboard write itself gates
 * the "Copied" state. */
export function ResultView({ text, onCopied }: ResultViewProps) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");

  function handleCopy() {
    if (!navigator.clipboard?.writeText) {
      setCopyState("error");
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => {
        setCopyState("copied");
        onCopied?.();
      },
      () => {
        setCopyState("error");
      },
    );
  }

  return (
    <div>
      <GeneratedTextRenderer text={text} />
      <button type="button" onClick={handleCopy}>
        {copyState === "copied" ? "Copied" : "Copy"}
      </button>
      {copyState === "error" ? (
        <p role="alert">Could not copy to clipboard. Please copy the text above manually.</p>
      ) : null}
    </div>
  );
}
