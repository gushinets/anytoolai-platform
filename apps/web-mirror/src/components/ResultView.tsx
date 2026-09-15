"use client";

import { useState } from "react";
import { GeneratedTextRenderer } from "@anytoolai/web-result-kit";

export type ResultViewProps = {
  text: string;
  /** Performs the actual copy (clipboard write, then any next-action recording); resolves `true`
   * iff the clipboard write itself succeeded. Product-specific (e.g. which next action to fire),
   * so it stays out of this shared component -- see `ProductDefinition.onCopy`. */
  onCopy?: (text: string) => Promise<boolean>;
};

/** Canonical text result plus a copy-to-clipboard button. The result stays visible and copyable
 * even if the copy fails -- only `onCopy`'s own outcome gates the "Copied" state. */
export function ResultView({ text, onCopy }: ResultViewProps) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");

  function handleCopy() {
    if (!onCopy) {
      setCopyState("error");
      return;
    }
    onCopy(text).then(
      (copied) => setCopyState(copied ? "copied" : "error"),
      () => setCopyState("error"),
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
