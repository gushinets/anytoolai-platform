import { useEffect, useLayoutEffect } from "react";

// `useLayoutEffect` is a no-op-with-a-warning during SSR (no DOM) -- Next.js still does an
// initial server render of "use client" components -- so this falls back to `useEffect` there and
// only upgrades to the synchronous, pre-paint timing in an actual browser (or jsdom, which defines
// `window`). Code review finding: `onBusyChange` firing from a plain `useEffect` runs *after* the
// browser could already have painted the settled result (Copy button visible) while the parent's
// own mirrored `busy` state was still stale, so a mode-switch click landing in that window was
// silently dropped -- `useLayoutEffect` flushes the whole child-fires-effect -> parent-setState ->
// parent-re-renders cascade synchronously, before that intermediate state is ever observable.
export const useIsomorphicLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;
