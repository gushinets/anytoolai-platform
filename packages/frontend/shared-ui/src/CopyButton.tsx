"use client";

import { useState, type ReactNode } from "react";
import { Button, type ButtonProps } from "./Button";

export type CopyButtonProps = Omit<ButtonProps, "onClick" | "children"> & {
  text: string;
  /** Called once the clipboard write itself succeeds -- which (if any) next action to fire after a
   * copy is caller-specific, so it stays out of this component. */
  onCopied?: () => void;
  children?: ReactNode;
};

/** The result stays visible and copyable even if `onCopied` (or whatever it triggers) fails --
 * only the clipboard write itself gates the "Copied" label. */
export function CopyButton({ text, onCopied, children = "Copy", variant = "secondary", ...props }: CopyButtonProps) {
  const [state, setState] = useState<"idle" | "copied" | "error">("idle");

  function handleClick() {
    if (!navigator.clipboard?.writeText) {
      setState("error");
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => {
        setState("copied");
        invokeOnCopied();
      },
      () => {
        setState("error");
      },
    );
  }

  // Neither a synchronous throw nor an async `onCopied`'s later rejection (TS's `() => void`
  // return type structurally accepts `() => Promise<void>`) may propagate as an unhandled
  // rejection or break the already-successful copy -- same reasoning as ProductRunPage's own
  // `emitEvent`.
  function invokeOnCopied(): void {
    try {
      Promise.resolve(onCopied?.()).catch(_noop);
    } catch {
      // onCopied threw synchronously -- nothing to attach a rejection handler to.
    }
  }

  return (
    <>
      <Button {...props} variant={variant} onClick={handleClick}>
        {state === "copied" ? "Copied" : children}
      </Button>
      {state === "error" ? <p role="alert">Could not copy to clipboard. Please copy the text above manually.</p> : null}
    </>
  );
}

function _noop(): void {
  // Deliberately discards a settled promise's rejection -- see invokeOnCopied()'s own comment.
}
