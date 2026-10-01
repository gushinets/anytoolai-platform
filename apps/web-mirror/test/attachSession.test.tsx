// The route-level handling of `?session=`: read once, removed from the address bar, restored for a
// reload in the same tab, and forgotten only when the person moves on from the session the page showed.
import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { readAttachSessionId, rememberAttachSession, useAttachSession } from "../src/products/runtime/attachSession";
import { canAttachTarget } from "../src/products/attachTargets";
import { draftDefinition } from "../src/products/acceptanceBuilder/AcceptanceBuilderProduct";
import { getRegisteredProduct } from "../src/products/registry";

beforeEach(() => {
  window.history.replaceState(null, "", "/products/acceptance_builder?session=s%201&keep=1");
});
afterEach(() => window.sessionStorage.clear());

describe("useAttachSession", () => {
  it("uses the URL id, strips it from the address bar (keeping other params) and remembers it for this tab", () => {
    const { result } = renderHook(() => useAttachSession("acceptance_builder", "s 1"));
    expect(result.current.attachSessionId).toBe("s 1");
    expect(window.location.search).toBe("?keep=1");
    expect(readAttachSessionId("acceptance_builder")).toBe("s 1");
  });

  it("restores the id after a reload (no URL param) until the person moves on from the shown session", () => {
    rememberAttachSession("acceptance_builder", "s 1", "2026-10-01T10:00:00Z");
    const reloaded = renderHook(() => useAttachSession("acceptance_builder", undefined));
    expect(reloaded.result.current.attachSessionId).toBe("s 1");

    reloaded.result.current.onAttachBegin?.();
    reloaded.result.current.onAttachEnd?.();
    const next = renderHook(() => useAttachSession("acceptance_builder", undefined));
    expect(next.result.current.attachSessionId).toBeUndefined();
  });

  it("forgets only the id it attached: a session stored meanwhile (a late Accept) survives the end", () => {
    rememberAttachSession("acceptance_builder", "s 1", "2026-10-01T10:00:00Z");
    const shown = renderHook(() => useAttachSession("acceptance_builder", undefined));
    shown.result.current.onAttachBegin?.();
    rememberAttachSession("acceptance_builder", "s 2", "2026-10-01T10:05:00Z");

    shown.result.current.onAttachEnd?.();
    expect(readAttachSessionId("acceptance_builder")).toBe("s 2");
  });

  it("forgets nothing for an end that was never preceded by a begin (a failed boot, another mode)", () => {
    rememberAttachSession("acceptance_builder", "s 1", "2026-10-01T10:00:00Z");
    const reloaded = renderHook(() => useAttachSession("acceptance_builder", undefined));
    reloaded.result.current.onAttachEnd?.();
    expect(readAttachSessionId("acceptance_builder")).toBe("s 1");
  });

  it("treats an empty URL value as no id, falling back to this tab's stored one", () => {
    rememberAttachSession("acceptance_builder", "s 1", "2026-10-01T10:00:00Z");
    expect(renderHook(() => useAttachSession("acceptance_builder", "")).result.current.attachSessionId).toBe("s 1");
    window.sessionStorage.clear();
    expect(renderHook(() => useAttachSession("acceptance_builder", "")).result.current.attachSessionId).toBeUndefined();
  });

  it("remembers only a NEWER accepted session: an older one settling late cannot replace it", () => {
    rememberAttachSession("acceptance_builder", "new", "2026-10-01T10:05:00Z");
    rememberAttachSession("acceptance_builder", "old", "2026-10-01T10:00:00Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("new");

    rememberAttachSession("acceptance_builder", "newest", "2026-10-01T10:10:00Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("newest");
  });

  it("keeps the rank of a session the consent page remembered when it arrives as ?session= (a late older one still loses)", () => {
    rememberAttachSession("acceptance_builder", "s 1", "2026-10-01T10:05:00Z");
    renderHook(() => useAttachSession("acceptance_builder", "s 1"));
    rememberAttachSession("acceptance_builder", "older", "2026-10-01T10:00:00Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("s 1");
  });

  it("is scoped per product", () => {
    rememberAttachSession("acceptance_builder", "s 1", "2026-10-01T10:00:00Z");
    expect(renderHook(() => useAttachSession("brief_decoder", undefined)).result.current.attachSessionId).toBeUndefined();
  });
});

describe("attach targets", () => {
  it("lists only what a registered product page can attach", () => {
    expect(getRegisteredProduct("acceptance_builder")).not.toBeNull();
    expect(canAttachTarget("acceptance_builder", draftDefinition.scenarioId)).toBe(true);
    expect(canAttachTarget("acceptance_builder", "acceptance_builder.check_v1")).toBe(false);
    expect(canAttachTarget("brief_decoder", "brief_decoder.decode_v1")).toBe(false);
  });
});
