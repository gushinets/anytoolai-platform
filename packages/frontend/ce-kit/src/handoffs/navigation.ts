/** Injectable navigation used by `openHandoffConsent()` to open the backend-owned consent URL. */
export type Navigate = (url: string) => void | Promise<void>;
