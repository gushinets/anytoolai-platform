import type { Linter } from "eslint";

export declare function baseConfig(options?: {
  tsconfigRootDir?: string;
  react?: boolean;
  ignores?: string[];
}): Linter.Config[];
