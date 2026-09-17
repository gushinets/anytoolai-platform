import { forwardRef, type SelectHTMLAttributes } from "react";
import styles from "./field.module.css";

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, children, ...props },
  ref,
) {
  return (
    <select ref={ref} {...props} className={[styles.field, className].filter(Boolean).join(" ")}>
      {children}
    </select>
  );
});
