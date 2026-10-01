/** Invokes a caller-supplied no-argument callback defensively, like `emitEvent` does for events: neither a
 * synchronous throw nor a rejected promise (a `() => void` prop can legally be async) may break the UI. */
export function callSafely(callback: (() => void | Promise<void>) | undefined): void {
  try {
    Promise.resolve(callback?.()).catch(() => undefined);
  } catch {
    // The callback threw synchronously: nothing to attach a rejection handler to.
  }
}
