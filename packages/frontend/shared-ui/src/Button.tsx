import type { ButtonHTMLAttributes } from "react";
import { Spinner } from "./Spinner";
import styles from "./Button.module.css";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary";
  /** Disables the button and shows a spinner ahead of its label, without changing the label
   * itself -- callers own the phase-specific label text (see `ProductRunPage`). */
  loading?: boolean;
};

export function Button({ variant = "primary", loading = false, disabled, className, children, ...props }: ButtonProps) {
  const variantClass = variant === "primary" ? styles.primary : styles.secondary;
  return (
    <button
      type="button"
      {...props}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={[styles.button, variantClass, className].filter(Boolean).join(" ")}
    >
      {loading ? <Spinner /> : null}
      {children}
    </button>
  );
}
