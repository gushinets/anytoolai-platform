# Proposal AI live local run

## Status

- State: completed
- Owner: agent
- Created: 2026-09-24
- Last updated: 2026-09-24
- Review date: 2026-09-25
- Next action: inspect the running product in a browser
- Blocker: none

## Goal

Run the current Proposal AI web UI and backend with the real OpenAI provider to inspect i18n.

## Steps

1. Temporarily point Proposal AI at the existing `default_text_generation_v1` provider policy for the local Docker build.
2. Validate product config, rebuild and start the Compose services with the local provider key.
3. Build and serve `web-mirror` against this checkout's API port.
4. Verify the UI, the configured provider, and one real scenario run.

## Result

- Backend images were built with `default_text_generation_v1`; API, worker and PostgreSQL remain running.
- `web-mirror` was built and served at `http://127.0.0.1:3100/products/proposal_ai`.
- One real scenario completed; its provider-call ledger row was `openai | gpt-5.4-nano-2026-03-17 | succeeded`.
- The source action config was restored to its original fake policy after the image build, to preserve the repository's deterministic test suite. Rebuilding backend images will restore fake behavior unless the live policy is selected again.
