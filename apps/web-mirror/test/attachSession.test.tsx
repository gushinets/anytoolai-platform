// The route-level handling of `?session=`: read once, removed from the address bar, restored for a
// reload in the same tab, and forgotten only when the person moves on from the session the page showed.
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { chooseAttachSession, preferSavedOwnRun, readAttachSessionId, rememberAttachSession, useAttachSession } from "../src/products/runtime/attachSession";
import { clearProductDraft, saveDraftRun } from "../src/products/runtime/draftStorage";
import { canAttachTarget } from "../src/products/attachTargets";
import { draftDefinition } from "../src/products/acceptanceBuilder/AcceptanceBuilderProduct";
import { getRegisteredProduct } from "../src/products/registry";

beforeEach(() => {
  window.history.replaceState(null, "", "/products/acceptance_builder?session=s%201&keep=1");
});
afterEach(() => window.sessionStorage.clear());

describe("useAttachSession", () => {
  it("keeps the URL until the resolved session is persisted, preserving other parameters", () => {
    const { result } = renderHook(() => useAttachSession("acceptance_builder", "s 1"));
    expect(result.current.attachSessionId).toBe("s 1");
    expect(readAttachSessionId("acceptance_builder")).toBeUndefined();
    expect(window.location.search).toContain("session=");
    act(() => result.current.onAttachResolved?.("s 1"));
    expect(window.location.search).toBe("?keep=1");
    expect(readAttachSessionId("acceptance_builder")).toBe("s 1");
  });

  it("consumes the linked scenario with the session and keeps the explicit choice until this visit ends", () => {
    window.history.replaceState(null, "", "/products/acceptance_builder?session=s1&scenario=acceptance_builder.check_v1&paid=1");
    const linked = renderHook(({ session }) => useAttachSession("acceptance_builder", session), { initialProps: { session: "s1" as string | undefined } });
    act(() => linked.result.current.onAttachResolved?.("s1"));
    expect(window.location.search).toBe("?paid=1");
    linked.rerender({ session: undefined });
    expect(linked.result.current.attachFromUrl).toBe(true);
    expect(linked.result.current.attachSessionId).toBe("s1");
    const reloaded = renderHook(() => useAttachSession("acceptance_builder", undefined));
    expect(reloaded.result.current.attachFromUrl).toBe(false);
    expect(reloaded.result.current.attachSessionId).toBe("s1");
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

  it.each([false, true])("explicitly discards before begin, including in-memory state (stored=%s)", (stored) => {
    if (stored) rememberAttachSession("acceptance_builder", "A", "2026-10-01T10:00:00Z");
    const { result, rerender } = renderHook(() => useAttachSession("acceptance_builder", stored ? undefined : "A"));
    act(() => result.current.onAttachDiscard?.());
    rerender();
    expect(result.current.attachSessionId).toBeUndefined();
    expect(readAttachSessionId("acceptance_builder")).toBeUndefined();
    expect(renderHook(() => useAttachSession("acceptance_builder", undefined)).result.current.attachSessionId).toBeUndefined();
  });

  it.each([false, true])("discard preserves a newer Accept arriving before the click (explicit older=%s)", (explicit) => {
    if (explicit) chooseAttachSession("acceptance_builder", "A", "2026-10-01T10:00:00Z");
    const { result } = renderHook(() => useAttachSession("acceptance_builder", "A"));
    const discard = result.current.onAttachDiscard;
    rememberAttachSession("acceptance_builder", "B", "2026-10-01T10:05:00Z");
    act(() => discard?.());
    expect(result.current.attachSessionId).toBeUndefined();
    expect(readAttachSessionId("acceptance_builder")).toBe("B");
    act(() => discard?.());
    expect(readAttachSessionId("acceptance_builder")).toBe("B");
  });

  it("discard preserves another active session and does not assign the discarded timestamp to it", () => {
    rememberAttachSession("acceptance_builder", "A", "2026-10-01T10:10:00Z");
    chooseAttachSession("acceptance_builder", "B", "2026-10-01T10:00:00Z");
    const { result } = renderHook(() => useAttachSession("acceptance_builder", "A"));
    act(() => result.current.onAttachDiscard?.());
    expect(readAttachSessionId("acceptance_builder")).toBe("B");
    rememberAttachSession("acceptance_builder", "C", "2026-10-01T10:05:00Z");
    const next = renderHook(() => useAttachSession("acceptance_builder", undefined));
    act(() => next.result.current.onAttachBegin?.());
    act(() => next.result.current.onAttachEnd?.());
    expect(readAttachSessionId("acceptance_builder")).toBe("C");
  });

  it("discard ignores a different stored active/newest session and leaves other products alone", () => {
    const { result } = renderHook(() => useAttachSession("acceptance_builder", "A"));
    chooseAttachSession("acceptance_builder", "B", "2026-10-01T10:00:00Z");
    rememberAttachSession("client_update_writer", "C", "2026-10-01T10:00:00Z");
    act(() => result.current.onAttachDiscard?.());
    expect(readAttachSessionId("acceptance_builder")).toBe("B");
    expect(readAttachSessionId("client_update_writer")).toBe("C");
  });

  it("a bare URL and its discard preserve an explicitly chosen session with unknown order", () => {
    chooseAttachSession("acceptance_builder", "B", "unknown");
    const { result } = renderHook(() => useAttachSession("acceptance_builder", "A"));
    expect(result.current.attachSessionId).toBe("A");
    expect(readAttachSessionId("acceptance_builder")).toBe("B");
    act(() => result.current.onAttachDiscard?.());
    expect(readAttachSessionId("acceptance_builder")).toBe("B");
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

  it("orders by time, not by string: a timestamp with fractional seconds is later than the same second without", () => {
    rememberAttachSession("acceptance_builder", "later", "2026-10-01T10:00:00.500000Z");
    rememberAttachSession("acceptance_builder", "earlier", "2026-10-01T10:00:00Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("later");

    window.sessionStorage.clear();
    rememberAttachSession("acceptance_builder", "earlier", "2026-10-01T10:00:00Z");
    rememberAttachSession("acceptance_builder", "later", "2026-10-01T10:00:00.500000Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("later");
  });

  it("orders timestamps that differ only below a millisecond (the backend's clock has microseconds), in either arrival order", () => {
    rememberAttachSession("acceptance_builder", "newer", "2026-10-01T10:00:00.000900Z");
    rememberAttachSession("acceptance_builder", "older", "2026-10-01T10:00:00.000100Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("newer");

    window.sessionStorage.clear();
    rememberAttachSession("acceptance_builder", "older", "2026-10-01T10:00:00.000100Z");
    rememberAttachSession("acceptance_builder", "newer", "2026-10-01T10:00:00.000900Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("newer");
  });

  it("keeps the rank of a session the consent page remembered when it arrives as ?session= (a late older one still loses)", () => {
    rememberAttachSession("acceptance_builder", "s 1", "2026-10-01T10:05:00Z");
    renderHook(() => useAttachSession("acceptance_builder", "s 1"));
    rememberAttachSession("acceptance_builder", "older", "2026-10-01T10:00:00Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("s 1");
  });

  it("keeps the previous selection until a bare link is verified, then makes it explicit", () => {
    rememberAttachSession("acceptance_builder", "newer", "2026-10-01T10:05:00Z");
    const linked = renderHook(() => useAttachSession("acceptance_builder", "chosen"));
    expect(readAttachSessionId("acceptance_builder")).toBe("newer");
    act(() => linked.result.current.onAttachResolved?.("chosen"));
    rememberAttachSession("acceptance_builder", "latest", "2026-10-01T10:10:00Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("chosen");
  });

  it("a session the person opens themselves replaces a newer remembered one, and a late older Accept still cannot replace it", () => {
    rememberAttachSession("acceptance_builder", "newer", "2026-10-01T10:05:00Z");
    chooseAttachSession("acceptance_builder", "chosen older", "2026-10-01T10:00:00Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("chosen older");

    rememberAttachSession("acceptance_builder", "late, older than newer", "2026-10-01T10:04:00Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("chosen older");
    // Its reload identity survives the bare `?session=` link the open navigates with.
    renderHook(() => useAttachSession("acceptance_builder", "chosen older"));
    expect(readAttachSessionId("acceptance_builder")).toBe("chosen older");
  });

  it("an explicitly opened older session does not destroy the newer accepted one: when it ends, the newer is restored", () => {
    rememberAttachSession("acceptance_builder", "B", "2026-10-01T10:05:00Z");
    chooseAttachSession("acceptance_builder", "A", "2026-10-01T10:00:00Z");
    const { result } = renderHook(() => useAttachSession("acceptance_builder", "A"));
    act(() => result.current.onAttachBegin?.());
    expect(readAttachSessionId("acceptance_builder")).toBe("A");

    act(() => result.current.onAttachEnd?.());
    expect(readAttachSessionId("acceptance_builder")).toBe("B");
    // B ending in turn leaves nothing behind.
    const second = renderHook(() => useAttachSession("acceptance_builder", undefined));
    act(() => second.result.current.onAttachBegin?.());
    act(() => second.result.current.onAttachEnd?.());
    expect(readAttachSessionId("acceptance_builder")).toBeUndefined();
  });

  it("a late older Accept leaves the fallback newest session alone, and a newer one replaces both", () => {
    rememberAttachSession("acceptance_builder", "B", "2026-10-01T10:05:00Z");
    chooseAttachSession("acceptance_builder", "A", "2026-10-01T10:00:00Z");
    rememberAttachSession("acceptance_builder", "A", "2026-10-01T10:00:00Z"); // same id again: keeps the fallback
    rememberAttachSession("acceptance_builder", "older", "2026-10-01T09:00:00Z");
    const { result } = renderHook(() => useAttachSession("acceptance_builder", undefined));
    act(() => result.current.onAttachBegin?.());
    act(() => result.current.onAttachEnd?.());
    expect(readAttachSessionId("acceptance_builder")).toBe("B");

    rememberAttachSession("acceptance_builder", "C", "2026-10-01T10:30:00Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("C");
  });

  it("a newer Accept that settles late while an explicitly opened older session is shown becomes the fallback, not the restored one", () => {
    rememberAttachSession("acceptance_builder", "B", "2026-10-01T10:05:00Z");
    chooseAttachSession("acceptance_builder", "A", "2026-10-01T10:00:00Z");
    const { result } = renderHook(() => useAttachSession("acceptance_builder", "A"));
    act(() => result.current.onAttachBegin?.());
    rememberAttachSession("acceptance_builder", "C", "2026-10-01T10:30:00Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("A");

    act(() => result.current.onAttachEnd?.());
    expect(readAttachSessionId("acceptance_builder")).toBe("C");
  });

  it.each([
    ["an empty entry", () => undefined],
    ["the already remembered newest", () => rememberAttachSession("acceptance_builder", "A", "2026-10-01T10:00:00Z")],
  ])("choosing the newest session (from %s) keeps it restored over a newer Accept that settles late; nothing is left once it ends", (_label, arrange) => {
    arrange();
    chooseAttachSession("acceptance_builder", "A", "2026-10-01T10:00:00Z");
    const { result } = renderHook(() => useAttachSession("acceptance_builder", "A"));
    act(() => result.current.onAttachBegin?.());
    rememberAttachSession("acceptance_builder", "B", "2026-10-01T10:05:00Z");
    expect(readAttachSessionId("acceptance_builder")).toBe("A");

    act(() => result.current.onAttachEnd?.());
    expect(readAttachSessionId("acceptance_builder")).toBe("B");
  });

  it("a chosen newest session that ends with nothing newer behind it leaves nothing", () => {
    chooseAttachSession("acceptance_builder", "A", "2026-10-01T10:00:00Z");
    const { result } = renderHook(() => useAttachSession("acceptance_builder", "A"));
    act(() => result.current.onAttachBegin?.());
    act(() => result.current.onAttachEnd?.());
    expect(readAttachSessionId("acceptance_builder")).toBeUndefined();
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

describe("accepted own-run selection", () => {
  const productId = "proposal_ai";
  const key = "anytoolai.product_draft.proposal_ai.generate";
  function saveOwnRun() {
    saveDraftRun(key, { scenarioSessionId: "own", input: { taskText: "Own task" } });
  }

  it("prefers the saved own run over old and late attachments without deleting other accepted sessions", () => {
    chooseAttachSession(productId, "A", "2026-10-01T10:00:00Z");
    rememberAttachSession(productId, "B", "2026-10-01T10:05:00Z");
    const attached = renderHook(() => useAttachSession(productId, undefined));
    act(() => attached.result.current.onAttachBegin?.());
    saveOwnRun();
    expect(preferSavedOwnRun(productId, key, "own")).toBe(true);
    act(() => attached.result.current.onAttachEnd?.());
    // The visible fallback stays attached in memory; only reload selection changes.
    expect(attached.result.current.attachSessionId).toBe("A");
    expect(readAttachSessionId(productId)).toBeUndefined();
    rememberAttachSession(productId, "C", "2026-10-01T10:10:00Z");
    expect(renderHook(() => useAttachSession(productId, undefined)).result.current.attachSessionId).toBeUndefined();
    clearProductDraft(key);
    expect(renderHook(() => useAttachSession(productId, undefined)).result.current.attachSessionId).toBe("C");
  });

  it("remembers a late attachment behind an own run even when there was no previous attachment", () => {
    saveOwnRun();
    expect(preferSavedOwnRun(productId, key, "own")).toBe(true);
    rememberAttachSession(productId, "late", "2026-10-01T10:10:00Z");
    expect(readAttachSessionId(productId)).toBeUndefined();
    clearProductDraft(key);
    expect(readAttachSessionId(productId)).toBe("late");
  });

  it.each(["consent", "url"])("an explicit %s attachment open supersedes an own run", (source) => {
    saveOwnRun();
    expect(preferSavedOwnRun(productId, key, "own")).toBe(true);
    if (source === "consent") chooseAttachSession(productId, "chosen", "2026-10-01T10:00:00Z");
    else {
      const linked = renderHook(() => useAttachSession(productId, "chosen"));
      expect(readAttachSessionId(productId)).toBeUndefined();
      act(() => linked.result.current.onAttachResolved?.("chosen"));
    }
    expect(renderHook(() => useAttachSession(productId, undefined)).result.current.attachSessionId).toBe("chosen");
  });

  it("never replaces an attachment with a missing or different stored own run", () => {
    chooseAttachSession(productId, "A", "2026-10-01T10:00:00Z");
    expect(preferSavedOwnRun(productId, key, "own")).toBe(false);
    saveOwnRun();
    expect(preferSavedOwnRun(productId, key, "other")).toBe(false);
    expect(readAttachSessionId(productId)).toBe("A");
  });

  it.each([null, {}, { key: 1, scenarioSessionId: "own" }, { key, scenarioSessionId: [] },
    { key: "anytoolai.product_draft.other.generate", scenarioSessionId: "own" }])("ignores an invalid own-run reference %j", (draft) => {
    window.sessionStorage.setItem(`anytoolai.attach_session.${productId}`, JSON.stringify({ id: "A", rank: 0, draft }));
    expect(readAttachSessionId(productId)).toBe("A");
  });
});
