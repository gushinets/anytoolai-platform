import { forwardRef, type InputHTMLAttributes } from "react";
import styles from "./field.module.css";

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ className, ...props }, ref) {
  return <input ref={ref} {...props} className={[styles.field, className].filter(Boolean).join(" ")} />;
});
