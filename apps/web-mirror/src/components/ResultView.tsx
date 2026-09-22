"use client";

import { useState } from "react";
import { Button, Card } from "@anytoolai/shared-ui";
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
  const [copyState, setCopyState] = useState<"idle" | "copying" | "copied" | "error">("idle");

  function handleCopy() {
    if (!onCopy) {
      setCopyState("error");
      return;
    }
    // Disables the button below for the duration of the copy -- code review finding: a fast
    // double-click had no guard against firing onCopy twice for the same result. A setState after
    // unmount (e.g. the page navigates away mid-copy) needs no guard of its own -- React 18+
    // already makes that a silent no-op, not a warning or an error.
    setCopyState("copying");
    onCopy(text).then(
      (copied) => setCopyState(copied ? "copied" : "error"),
      () => setCopyState("error"),
    );
  }

  return (
    <Card>
      <GeneratedTextRenderer text={text} />
      <Button variant="secondary" onClick={handleCopy} disabled={copyState === "copying"}>
        {copyState === "copied" ? "Copied" : copyState === "copying" ? "Copying…" : "Copy"}
      </Button>
      {copyState === "error" ? (
        <p role="alert">Could not copy to clipboard. Please copy the text above manually.</p>
      ) : null}
    </Card>
  );
}
