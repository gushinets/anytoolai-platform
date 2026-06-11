# Repo Navigation

## To add platform runtime code

Use `packages/backend/platform-core`.

## To add a generic atom/action

Use `packages/backend/platform-actions` and `configs/kernel/action_definitions`.

## To add product-specific behavior

Use `packages/backend/product-platforms/<bundle>` and never platform-core.

## To add Chrome Extension behavior

Use `extensions/<product-ce>` and shared helpers in `packages/frontend/ce-kit`.

## To add docs

Use `docs/`. Link from `docs/index.md`.
