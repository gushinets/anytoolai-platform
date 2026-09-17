import type { ReactNode } from "react";
import styles from "./Toast.module.css";

export type ToastProps = {
  variant: "success" | "error";
  children: ReactNode;
};

/** No `warning` variant: `tokens.json` has no `warningBackground`/`warningBorder` pair and nothing
 * currently needs one -- see the exec-plan's design-decisions log. */
export function Toast({ variant, children }: ToastProps) {
  return (
    <div role={variant === "error" ? "alert" : "status"} className={[styles.toast, styles[variant]].join(" ")}>
      {children}
    </div>
  );
}
