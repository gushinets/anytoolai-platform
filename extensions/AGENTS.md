# Extension Rules

- Extensions are product-specific shells.
- Use `packages/frontend/ce-kit` for API calls.
- Do not store system prompts.
- Do not choose provider/model.
- Do not invent workflows or next actions.

- `pnpm --filter @anytoolai/kernel-demo-ce dev` (from the repo root, or `pnpm dev` inside the extension directory) rebuilds `.output/chrome-mv3-dev` but does not open a browser (`web-ext` is intentionally not installed); load it in Chrome via "Load unpacked". Do not run `wxt dev`: in WXT 0.21 `dev` is read as the project root.
