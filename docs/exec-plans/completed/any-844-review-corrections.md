# Execution Plan: ANY-844 Review Corrections

## Status

- State: completed
- Owner: agent
- Created: 2026-11-12
- Last updated: 2026-11-12
- Review date: 2026-11-12
- Next action: Review the fixes and supply the approved policy URL before public deployment.
- Blocker: None for implementation; the approved production policy URL remains operator-owned.

## Goal and scope

Reject a missing or invalid policy URL before public deployment starts, without changing optional
URL handling in development, fake production smoke or maintenance commands. Correct the seven
shared translations so products without draft recovery do not promise tab-lifetime persistence.

## Baseline and decisions

- Branch `feature/ANY-844`, checked head `95062000c839574f83235504339e9a651243e704`.
- Read both PR #269 inline findings and the current Linear acceptance criteria. Live deployment
  input validation accepted missing/empty/relative/unsafe-scheme URLs in a side-effect-free probe.
- Brief Decoder, Task Finder and both Acceptance Builder modes have no draft opt-in; only
  ProposalAI and the three Client Update Writer modes enable tab-storage draft recovery.
- Use the standard Node.js URL parser already required on deployment hosts, matching the browser's
  absolute HTTP(S) acceptance. Invoke only from prod-up before profile creation or Docker calls.
  No policy fetch or legal-content approval is inferred from syntax validation.
- Keep the common production Compose build argument optional: fake smoke and maintenance share it.
- Replace the unconditional draft-lifetime claim with a shared warning that browser drafts may be
  lost on reload or navigation. No new product branches or persistence functionality.

## Implementation plan

- [x] Add public-deploy URL preflight and update deployment instructions.
- [x] Test missing/invalid/valid URLs, validator failure, and optional fake/maintenance paths.
- [x] Correct all seven locales and verify a real non-persistent product through remount.
- [x] Run focused runner/web regressions, lint/typecheck, docs/config/architecture checks.
- Commit and push to the existing branch, as explicitly authorized by the user, after final diff validation.

## Verification

- Managed Python 3.12 doctor passes with Node 24 and pinned pnpm 10.34.1.
- Production/fake/maintenance runner regressions: 113 passed, 188 deselected. Includes malformed
  schemes/hosts/ports, absent and blank values, Unicode trimming, valid URL forwarding, missing
  Node/timeout failure, and fake smoke with missing/invalid URLs.
- All 699 web-host tests pass; TypeScript and ESLint pass. The new Brief Decoder regression keeps
  browser storage across remount, proves unsent input is lost, and checks the truthful warning.
- Actual Docker Compose config rendering passes with no policy URL (empty build arg for smoke)
  and with a configured policy URL (exact build-arg forwarding); no containers were started.
- Documentation, architecture, config validation and generated-doc drift checks pass.
- Initial sandboxed runner tests failed on deployment-lock directory ownership checks. The
  unrestricted rerun passes. Generated docs also pass outside the sandbox after restricted
  network access triggered an unrelated LiteLLM import error.
- Production code changes are confined to public-deploy preflight and seven shared translations.
  Full backend/provider suites and live production were not rerun for these corrections.

## Windows CI follow-up

- Windows baseline job 131120770803 failed only the two validator-unavailable test cases:
  their global subprocess failure also intercepted PowerShell deployment-lock ACL inspection.
- Restrict the failure stub to Node evaluation and delegate other commands to the real
  subprocess runner. Keep production validation and lock protections unchanged.
- The complete runner test module reaches completion locally with one unrelated environment
  failure: the activation-marker test requires passwordless sudo to run as nobody. Native
  Windows ACL execution remains a CI check.
- Production/fake/maintenance regressions pass: 113 passed, 188 deselected. Documentation
  validation and diff whitespace checks pass. Existing local-skill references in unrelated
  execution plans were left outside this correction.

## Review round 2: precise input warning

- The shared prohibition on all sensitive/confidential information conflicted with Client Update
  Writer's client-message and payment-term inputs. Narrow the final sentence in all seven locales
  to passwords, access codes, API keys and full payment-card details, as approved by the user.
- Preserve the processing, storage, draft and policy-link text. No new runtime behavior or
  dependencies; existing notice and product tests cover rendering and submission integration.
- Validation: all 699 web-host tests, TypeScript, ESLint and documentation checks pass.
  JSON comparison confirms only the final warning sentence changed in each locale.

## Risks and limits

The operator must still provide the approved policy URL and confirm the page is available and
current. Validation checks syntax only. No production deployment or data-retention change.
