import { cleanup, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PortalIdentityBoundary } from "../src/components/PortalIdentityBoundary";
import { getPlatformApiClient } from "../src/lib/apiClient";
import { getPortalIdentity } from "../src/lib/portalSession";
import { makeRender, englishForAllLocales } from "./support/renderWithI18n";

afterEach(cleanup);
it("a paid deep link in a fresh tab requires authorization before any guest or product mount", async () => {
  const child = vi.fn(() => <p>Private product</p>);
  const render = makeRender(englishForAllLocales({}));
  const view = render(<PortalIdentityBoundary requirePaid>{child}</PortalIdentityBoundary>);
  expect(await screen.findByText("Sign in again to continue the same operation.")).toBeTruthy();
  expect(child).not.toHaveBeenCalled();
  expect(getPortalIdentity().kind).toBe("required");
  expect(() => getPlatformApiClient()).toThrow("portal_authorization_required");
  // Removing the query on client navigation cannot turn this paid tab into a guest.
  view.rerender(<PortalIdentityBoundary>{child}</PortalIdentityBoundary>);
  expect(child).not.toHaveBeenCalled();
});
