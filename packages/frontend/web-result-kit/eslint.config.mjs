import { baseConfig } from "../../../eslint.config.base.mjs";

export default baseConfig({ tsconfigRootDir: import.meta.dirname, react: true });
