"use client";

import { useState, type ReactNode } from "react";
import { Button, Card, Toast } from "@anytoolai/shared-ui";
import { GeneratedTextRenderer } from "@anytoolai/web-result-kit";
import { useHostT } from "../i18n";
import styles from "./cardStack.module.css";

export type ResultViewProps = {
  text: string;
  /** Render inside an existing Card without adding a second card surface. */
  embedded?: boolean;
  /** Performs the actual copy (clipboard write, then any next-action recording); resolves `true`
   * iff the clipboard write itself succeeded. Product-specific (e.g. which next action to fire),
   * so it stays out of this shared component -- see `ProductDefinition.onCopy`. */
  onCopy?: (text: string) => Promise<boolean>;
  secondaryAction?: ReactNode;
};

/** Canonical text result plus a copy-to-clipboard button. The result stays visible and copyable
 * even if the copy fails -- only `onCopy`'s own outcome gates the "Copied" state. */
export function ResultView({ text, onCopy, embedded = false, secondaryAction }: ResultViewProps) {
  const t = useHostT();
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

  const Container = embedded ? "div" : Card;
  const copyButton = (
    <Button variant="secondary" onClick={handleCopy} disabled={copyState === "copying"}>
      {copyState === "copied" ? t("result.copied") : copyState === "copying" ? t("result.copying") : t("result.copy")}
    </Button>
  );
  return (
    <Container className={styles.stack}>
      <GeneratedTextRenderer text={text} />
      {secondaryAction ? <div className={styles.actions}>{copyButton}{secondaryAction}</div> : copyButton}
      {copyState === "error" ? (
        <Toast variant="error">{t("result.copyFailed")}</Toast>
      ) : null}
    </Container>
  );
}
