# VPS Release Runbook

VPS 135 runs `anytoolai-prod` and `anytoolai-atom-lab` as separate Compose projects behind
the Payment Portal Caddy. Each project has its own API, worker, and PostgreSQL volume.

## Before the maintenance window

1. Record the running and candidate Git commits, checkout paths, image IDs, and Alembic
   revisions. Save the working Caddyfile and HTTP statuses for affected routes and neighboring
   services. Check CI on the candidate commit.
2. Clone into a private release directory with parent mode `0700`. Run `git clone` under
   `umask 022` so the web image can read the copied source as user `node`. Keep secret env
   files at `0600`. A checkout made under `umask 077` can build as root and then fail with
   `MODULE_NOT_FOUND` when the container starts.
3. Bootstrap Python from the candidate checkout. If using the tools installed in
   `/opt/anytoolai-tools/bin` on VPS 135, include that directory in `PATH`.

   ```bash
   python3 scripts/agent/runner.py quick-check --bootstrap-only &&
     .quick-check-venv/bin/python scripts/agent/runner.py doctor
   ```

   If the system Python reports `ensurepip is not available`, initialize the environment with
   `uv venv --allow-existing --python "$(command -v python3)" .quick-check-venv` and rerun
   the bootstrap.
4. For a product update, prepare `.env.prod` with the approved `ANYTOOLAI_PRIVACY_POLICY_URL`
   and verify the page opens. This URL, the enabled product list, and the web base path are
   build arguments. Use the same checkout, environment, and VPS build arguments for the
   prebuild and `prod-up`. The live overlay adds runtime settings and mounts.
   [Production settings](README.md#prod)

   ```bash
   COMPOSE_PARALLEL_LIMIT=1 docker compose --project-name anytoolai-release-prebuild \
     --env-file infra/compose/.env.prod \
     -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml \
     -f infra/compose/docker-compose.vps-135.yml \
     build migrate platform-api platform-worker web-mirror &&
   docker run --rm --pull never --network none --entrypoint node \
     anytoolai-release-prebuild-web-mirror node_modules/next/dist/bin/next --version
   ```

   For `MODULE_NOT_FOUND`, correct the checkout permissions and repeat the build and probe.
   If Next.js stalls while fetching fonts, check access to `fonts.googleapis.com` and
   `fonts.gstatic.com` from the Docker build network and retry before closing ingress.

## Reload or restore Caddy on VPS 135

The host file is `/opt/payments-portal/deploy/caddy/Caddyfile.prod`. The container reads
`/etc/caddy/Caddyfile`. Use this procedure for maintenance, cutover, and rollback.

1. Save the working file. Validate the candidate before installing it and compare the
   host and container checksums. If they already differ, establish the working baseline
   before refreshing the mount.

   ```bash
   docker exec -i payments-portal-prod-caddy-1 \
     caddy validate --config /dev/stdin --adapter caddyfile \
     < "${candidate_caddyfile:?Set the candidate Caddyfile path}"
   sha256sum "$candidate_caddyfile" /opt/payments-portal/deploy/caddy/Caddyfile.prod
   docker exec payments-portal-prod-caddy-1 sha256sum /etc/caddy/Caddyfile
   ```

2. Write the validated candidate into the existing host file in place to preserve its inode.
   Compare the candidate, host, and container checksums. If they match, validate and reload
   the mounted file.

   ```bash
   docker exec payments-portal-prod-caddy-1 \
     caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile &&
   docker exec payments-portal-prod-caddy-1 \
     caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
   ```

3. If the mounted copy is stale, recreate only Caddy from `/opt/payments-portal` and
   verify the mounted checksum again.

   ```bash
   docker compose --project-name payments-portal-prod -f docker-compose.prod.yml \
     up -d --no-deps --force-recreate caddy
   ```

4. Check the changed routes and compare Payment Portal, PromptTune, and extension statuses
   with the baseline. If a route regresses, restore the saved Caddyfile and repeat the checks.

## Switch the stacks and verify

1. For each stack you update, close its ingress and quiesce it from the running checkout.
   Keep Lab's route ahead of any product maintenance response for `/tools/*` or `/v1/*`.
   Save a fresh PostgreSQL dump. For a schema change, restore that dump into an isolated
   database and run the candidate migrator there first. Verify the Alembic revision, row
   counts, and checksums for the preserved data.
   [Migration rehearsal and database rollback](execution-metering-cutover.md)
2. Run `prod-quiesce` to drain the product queue, then `prod-down` from the running checkout
   after backup and any migration rehearsal. Run `prod-up` and `prod-ready` from the
   candidate. Keep the named volume. Check the enabled product pages and runtime-config
   endpoints, then run one known scenario per enabled product. Reopen and verify product
   ingress before switching Lab.
3. Update Lab using `atom-lab-quiesce`, its [backup procedure](README.md#backup-recovery-and-rollback),
   and `atom-lab-down` from the running checkout. Use `atom-lab-up` and `atom-lab-ready`
   from the candidate.
   Check the Lab HTTPS page, assets, code protection, and one known synthetic run.
   [Atom Lab settings and ingress](README.md#atom-lab-on-vps-135)
4. On a failed product cutover, keep product ingress closed and verify the actual Alembic
   revision. The migrator can succeed before the web container fails. If cleanup stopped
   the candidate, use `prod-recovery-postgres-up` to inspect the schema. Restart the prior
   checkout with its matching settings if its code supports that schema. Otherwise restore
   the verified pre-release dump into a new database before starting the old code.
   [Product database rollback](execution-metering-cutover.md#failure-and-rollback)
5. On a Lab-only failure, restore the Caddyfile with product routes working and Lab closed.
   Quiesce Lab before stopping it and preserve its volume. Follow the Lab recovery procedure
   if its schema changed. [Lab database rollback](README.md#backup-recovery-and-rollback)

[November 12 release record](../../docs/exec-plans/completed/four-products-and-atom-lab-release.md)
