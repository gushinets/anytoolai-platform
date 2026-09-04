import { makeEnumGuard } from "../api/parsing";
import type { components } from "../api/generated/platformApi";

export type FrontendType = components["schemas"]["FrontendType"];

export const isFrontendType = makeEnumGuard<FrontendType>({
  chrome_extension: true,
  web: true,
});
