"use client";

import { useEffect, useRef, useState } from "react";
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
  // Guards a stale setState after unmount (e.g. the result page navigates away while onCopy is
  // still in flight) -- code review finding. Set `true` inside the effect body itself, not only
  // via the initial `useRef(true)`: React StrictMode's dev-only mount -> cleanup -> remount runs
  // this same cleanup once before the real, lasting mount -- without resetting it back to `true`
  // here, the ref would stay permanently `false` for the whole rest of that component instance's
  // life, silently dropping every future setCopyState (same fix shape as ProductRunPage's own
  // `controllerRef` effect, for the same StrictMode reason).
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  function handleCopy() {
    if (!onCopy) {
      setCopyState("error");
      return;
    }
    // Disables the button below for the duration of the copy -- code review finding: a fast
    // double-click had no guard against firing onCopy twice for the same result.
    setCopyState("copying");
    onCopy(text).then(
      (copied) => {
        if (isMountedRef.current) setCopyState(copied ? "copied" : "error");
      },
      () => {
        if (isMountedRef.current) setCopyState("error");
      },
    );
  }

  return (
    <div>
      <GeneratedTextRenderer text={text} />
      <button type="button" onClick={handleCopy} disabled={copyState === "copying"}>
        {copyState === "copied" ? "Copied" : copyState === "copying" ? "Copying…" : "Copy"}
      </button>
      {copyState === "error" ? (
        <p role="alert">Could not copy to clipboard. Please copy the text above manually.</p>
      ) : null}
    </div>
  );
}
