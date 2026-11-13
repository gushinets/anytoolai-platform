# November 12 Deployment Record

## Status

- State: completed
- ANY-468 acceptance: post-restart readback pending
- Owner: mixed
- Created: 2026-11-12
- Last updated: 2026-11-13

On November 12, 2026, commit `3ec2ea3c9d8e333f5aa0d5f794ab6163bbe48eb4` went live on
VPS `yasmine`. The product stack and Atom Lab ran as separate Compose projects and reached
Alembic revision `0018`. Products reopened at 16:36 UTC and Lab rollout checks ended at 16:39 UTC.
This record covers the completed deployment window. ANY-468 still has a post-restart acceptance
check in the [active Atom Lab plan](../active/atom-lab-v1.md#al10--any-468-atom-lab-v1-compose-deployment).
[Release PR](https://github.com/gushinets/anytoolai-platform/pull/273) ·
[CI on the deployed commit](https://github.com/gushinets/anytoolai-platform/actions/runs/43254030419)

- The production dump was restored into an isolated PostgreSQL database and migrated from
  `0015` to `0018`. Row counts and checksums over the original columns matched for 14 tables.
  The pre-release dump, checkout, and Caddy configuration were retained for rollback.
- ProposalAI, Client Update Writer, Brief Decoder, and Acceptance Builder returned HTTP `200`
  on their pages and runtime-config endpoints. One live run per product completed without
  consuming guest quota.
- Atom Lab opened over HTTPS under the operator-approved VPS 135 shared-code profile, with
  limits of 400 accepted runs per UTC day and eight queued or running jobs. A run with
  synthetic input went through the API and worker and succeeded with a real OpenAI
  `gpt-5-mini-2025-08-07` call recorded in the provider ledger. A second browser context
  could read the saved run and preset. The protected `lab-smoke.json` release artifact
  records the provider result and both IDs.
- Post-restart readback is outstanding. The release checked the run and preset while the
  same API and worker processes were still running.
- Payment Portal, PromptTune, and extension endpoints matched their pre-release HTTP statuses.

Use the [VPS release runbook](../../../infra/deployment/vps-release-runbook.md) for the next
release and for independent product or Lab rollback.
