import { forwardRef, type TextareaHTMLAttributes } from "react";
import styles from "./field.module.css";

export type TextAreaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(function TextArea(
  { className, ...props },
  ref,
) {
  return <textarea ref={ref} {...props} className={[styles.field, className].filter(Boolean).join(" ")} />;
});
