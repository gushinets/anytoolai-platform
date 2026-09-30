// The route-level handling of `?session=`: read once, removed from the address bar, restored for a
// reload in the same tab, and dropped once the user starts their own work.
import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useAttachSession } from "../src/products/runtime/attachSession";
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
    expect(window.sessionStorage.getItem("anytoolai.attach_session.acceptance_builder")).toBe("s 1");
  });

  it("restores the id after a reload (no URL param) until the user starts their own work", () => {
    window.sessionStorage.setItem("anytoolai.attach_session.acceptance_builder", "s 1");
    const reloaded = renderHook(() => useAttachSession("acceptance_builder", undefined));
    expect(reloaded.result.current.attachSessionId).toBe("s 1");

    reloaded.result.current.endAttach();
    const next = renderHook(() => useAttachSession("acceptance_builder", undefined));
    expect(next.result.current.attachSessionId).toBeUndefined();
  });

  it("is scoped per product", () => {
    window.sessionStorage.setItem("anytoolai.attach_session.acceptance_builder", "s 1");
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
