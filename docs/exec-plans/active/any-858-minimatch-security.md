# ANY-858: resolved lint dependency security

## Status

- State: active
- Owner: Codex
- Created: 2026-11-27
- Last updated: 2026-11-27
- Review date: 2026-11-27
- Next action: Finish final-commit verification and review handoff.
- Blocker: Docker daemon unavailable; PostgreSQL maintenance URL not configured.
- Baseline: freshly fetched origin/main `26128baa3ae87ad9213906af18697feafff28470`.
- Branch: `codex/any-858-minimatch`.

## Goal and boundaries

Remove all known applicable minimatch CVE/GHSA version matches from the complete resolved lint graph, with the smallest supported change. Keep the lint stack, scanning policy, allowBuilds and unrelated dependencies. No PR, merge, deployment, Linear mutation or alert closure is authorized. Personal timing remains only in the original checkout's ignored workpaper.md.

Read AGENTS.md, its ten start documents, docs/agent/coding-conventions.md, .github/workflows/{backend,frontend,trivy}.yml and completed/trivy-dependabot-adoption-2026-11-03.md. Root manifests and this plan have no governing nested AGENTS.md; extensions/AGENTS.md is not changed. No API, DB, configuration-runtime, event or product contract changes.

## Decision

Upgrade root devDependency floors to ESLint `^10.15.0` and typescript-eslint `^8.73.0`, locked at 10.15.0/8.73.0. Normal pnpm 10.34.1 resolution chooses minimatch 11.0.9 for all three direct lint consumers: ESLint, @eslint/config-array 0.23.7 and @typescript-eslint/typescript-estree 8.73.0. The independent OpenAPI generator copy remains 5.1.9, outside all checked affected ranges.

8.73.0 already changes typescript-estree's dependency to `^11.0.1`; 8.72.1 still declares `^10.2.2`. Therefore the proposed 8.74.0 is unnecessary for this fix. ESLint 10.14.0 still declares `^10.2.6`; 10.15.0 switches to `^11.0.5` and requires config-array `^0.23.6` (also `^11.0.5`). No override is needed: 11.0.9 satisfies every consumer's declared range. Forcing 11 into the old consumers would cross their major-version contracts without benefit over these supported releases.

[ESLint 10.15.0 release](https://github.com/eslint/eslint/releases/tag/v10.15.0), [typescript-eslint 8.73.0 package](https://registry.npmjs.org/typescript-eslint/8.73.0), [estree 8.73.0 package](https://registry.npmjs.org/@typescript-eslint/typescript-estree/8.73.0), [estree 8.72.1 package](https://registry.npmjs.org/@typescript-eslint/typescript-estree/8.72.1), [minimatch 11.0.9 release](https://github.com/isaacs/minimatch/releases/tag/v11.0.9).

## Decision matrix

E = ESLint direct path; C = ESLint → config-array; S = typescript-eslint → typescript-estree (including parser/plugin/utils routes). Every row also retains generator path O → D → minimatch 5.1.9. Exact path/range proof follows below. Advisory IDs in this matrix denote affected package versions; exposure conditions are assessed separately.

| ESLint version | typescript-eslint version | Other required package versions | Resolved minimatch paths and versions | Peer/Node compatibility | Validation status | Applicable CVE / GHSA |
|---|---|---|---|---|---|---|
| 10.9.1 | 8.69.0 | C 0.23.5, S 8.69.0 | E/C/S 10.2.6; generator 5.1.9 | Node 24, TS 5.9.3 supported | Baseline frozen install and lint pass; fresh Trivy reproduces Medium CVE | CVE-2026-118764 / GHSA-g3hv-75wg-m249; GHSA-c859-jr93-m5j4 |
| 10.14.0 | 8.72.1 | Older PRs, S requires ^10.2.2 | E/S still 10.2.6; both PR HEAD locks contain 10.2.6 and 5.1.9 | Compatible peers do not fix vulnerable dependency ranges | Current PR HEAD locks inspected; not selected or runtime-tested | Same CVE and GHSA as baseline |
| 10.15.0 | 8.69.0 | C 0.23.7, S 8.69.0 | E/C 11.0.9; S 10.2.6 | Compatible Node/peers | Independently resolved via pinned pnpm; rejected before runtime tests | CVE-2026-118764 and GHSA-c859 remain on S |
| 10.9.1 | 8.74.0 | C 0.23.5, S 8.74.0 | E/C 10.2.6; S 11.0.9 | Compatible Node/peers | Independently resolved via pinned pnpm; rejected before runtime tests | CVE-2026-118764 and GHSA-c859 remain on E/C |
| 10.15.0 | 8.74.0 | C 0.23.7, S 8.74.0 | E/C/S 11.0.9 | Compatible Node/peers | Independently resolved; viable, larger TS upgrade; no full runtime test claimed | None in resolved minimatch copies |
| **10.15.0** | **8.73.0** | **C 0.23.7, S 8.73.0** | **E/C/S 11.0.9; generator 5.1.9** | **Node 24.19.0 and TS 5.9.3 supported** | **Selected; frozen install/lint and fresh all-severity scan verified before commit; final-SHA checks recorded separately** | **None in resolved minimatch copies** |
| 10.15.0 | 8.73.0 | Hypothetical S-only 11.0.1 pin; E/C remain 11.0.9 | S 11.0.1 fixes ticket CVE but has other findings | S accepts ^11.0.1; E/C require ^11.0.5 | Manifest/advisory analysis only; rejected; no override applied | GHSA-cf2h-pxjq-68xw; GHSA-c859-jr93-m5j4 |
| 10.15.0 | 8.73.0 | Hypothetical 11.0.7 pin | E/C/S 11.0.7 fixes ticket CVE and compile regression | In every declared range | Manifest/advisory analysis only; rejected; no override applied | GHSA-hqmv-qgp3-jx75; GHSA-c859-jr93-m5j4 |
| 10.16.0 | 8.74.0 | Current npm latest releases still require minimatch | E ^11.0.5; S ^11.0.1; would admit 11.0.9 | Compatible Node/peers | Official manifests checked; newer ESLint unnecessary; not installed | No finding when resolved to 11.0.9; ranges alone do not prove safety |

All ESLint 10 rows use Node `^20.19.0 || ^22.13.0 || >=24`. typescript-eslint 8.73/8.74 use Node `^18.18.0 || ^20.9.0 || >=21.1.0`, ESLint peers `^8.57.0 || ^9.0.0 || ^10.0.0`, TypeScript `>=4.8.4 <6.1.0`. minimatch 11 requires Node `20 || >=22`, satisfied by .nvmrc 24. @eslint/js 10.0.1 and react-hooks 7.1.1 already accept ESLint 10. Estree's new @typescript/native peer is optional; no native compiler installation is required.

No supported minimatch-free pair was found. npm's current ESLint latest 10.16.0 directly requires `^11.0.5`; maintenance 9.39.5 directly requires `^3.1.5`. Current typescript-eslint 8.74.0 directly includes estree, which requires `^11.0.1`. The selected earlier versions also depend directly on minimatch. Removing it would require changing the lint stack or upstream implementations, outside ANY-858; retaining patched versions is sufficient. Evidence: [ESLint latest manifest](https://registry.npmjs.org/eslint/10.16.0), [maintenance manifest](https://registry.npmjs.org/eslint/9.39.5), [estree latest manifest](https://registry.npmjs.org/@typescript-eslint/typescript-estree/8.74.0).

## Advisory review

Queried both the global GitHub npm advisory API and the minimatch repository's public security-advisories API on 2026-11-27. The global API returns six reviewed advisories and omits the three November GHSA-only upstream records. Trivy's absence of a CVE is therefore supplemented with the upstream range review, not used alone as proof.

| Advisory | Relevant affected range / first patch | Trigger / applicability |
|---|---|---|
| [GHSA-g3hv-75wg-m249 / CVE-2026-118764](https://github.com/advisories/GHSA-g3hv-75wg-m249) | >=7.0.0 <11.0.1 / 11.0.1 | Pattern amplification with optimizationLevel >=2 and attacker-influenced glob segments. Baseline 10.2.6 matches; final copies do not. |
| [GHSA-cf2h-pxjq-68xw](https://github.com/isaacs/minimatch/security/advisories/GHSA-cf2h-pxjq-68xw) (no CVE) | 11.0.0–11.0.6 / 11.0.7 | Long wildcard path compilation can grow quadratically even through new Minimatch. 11.0.1 is insufficient. |
| [GHSA-hqmv-qgp3-jx75](https://github.com/isaacs/minimatch/security/advisories/GHSA-hqmv-qgp3-jx75) (no CVE) | 11.0.3–11.0.7 / 11.0.8 | Top-level minimatch() retains large unique expanded patterns in a global cache. Direct constructor use avoids this specific global retention. |
| [GHSA-c859-jr93-m5j4](https://github.com/isaacs/minimatch/security/advisories/GHSA-c859-jr93-m5j4) (no CVE) | 7.4.0–11.0.7 / 11.0.8 | escape() does not consistently preserve literal matching with leading negation/comments, braces/backslashes or certain Windows options. This requires caller use of escape() as a literalization boundary. |
| [GHSA-3ppc-4f35-3m26 / CVE-2026-26996](https://github.com/advisories/GHSA-3ppc-4f35-3m26) | 10 <10.2.1; 5 <5.1.7; older major ranges in source | Repeated wildcard patterns and failing literal match can cause backtracking. Both baseline copies are already patched for this finding. |
| [GHSA-7r86-cg39-jmmj / CVE-2026-27903](https://github.com/advisories/GHSA-7r86-cg39-jmmj) | 10 <10.2.3; 5 <5.1.8; older major ranges in source | Multiple non-adjacent globstars cause combinatorial matchOne backtracking. Baseline and final copies outside ranges. |
| [GHSA-23c5-xmqv-rm74 / CVE-2026-27904](https://github.com/advisories/GHSA-23c5-xmqv-rm74) | 10 <10.2.3; 5 <5.1.8; older major ranges in source | Nested extglobs can generate backtracking regexes. Baseline and final copies outside ranges. |
| [GHSA-f8q6-p94x-37v3 / CVE-2022-3517](https://github.com/advisories/GHSA-f8q6-p94x-37v3) | <3.0.5 / 3.0.5 | Historical regex denial of service; no baseline/final copy matches. |
| [GHSA-hxm2-r34f-qmc5 / CVE-2016-10540](https://github.com/advisories/GHSA-hxm2-r34f-qmc5) | <3.0.2 / 3.0.2 | Historical regex denial of service; no baseline/final copy matches. |

These are dependency version findings, not evidence of exploitation. Lint inputs are repository source/configuration, not an exposed product glob API. Config-array uses cached Minimatch constructors. No claim of reachable production exploitation is made, and no advisory is dismissed merely because this is development tooling. The fix removes every version match regardless of whether each trigger is reachable in today's lint configuration.

## Current remote state

- [PR #238](https://github.com/gushinets/anytoolai-platform/pull/238): closed, unmerged; HEAD `47bf477e6f39b43ec4112dbdea96bf6350e74e55`, ESLint 10.14.0. Lock inspected at this SHA still includes minimatch 10.2.6 and 5.1.9.
- [PR #248](https://github.com/gushinets/anytoolai-platform/pull/248): closed, unmerged; HEAD `a06d1b3013b257f7523a2879d26923beaf1ef94b`, typescript-eslint 8.72.1. Lock inspected at this SHA still includes 10.2.6 and 5.1.9.
- [Dependabot #181](https://github.com/gushinets/anytoolai-platform/security/dependabot/181): open at read time, transitive development minimatch 10.2.6, GHSA-g3hv-75wg-m249.
- [Trivy #63](https://github.com/gushinets/anytoolai-platform/security/code-scanning/63): already marked fixed; most recent instance references main commit `06d79037316be9c76dff61c1b5349b502b19b5f6`, updated 2026-11-18. This remote state does not prove the current baseline lock safe: the fresh local baseline scan reproduces the CVE.
- Read-only authenticated APIs were used; no alert or issue mutation occurred.

## Implementation and rollback

Changed files: package.json (two devDependency floors), pnpm-lock.yaml (generated by `corepack pnpm add --workspace-root --save-dev eslint@10.15.0 typescript-eslint@8.73.0`), this plan. No handwritten lock edits. @eslint/config-array resolves 0.23.7. The additional cache packages are required by ESLint's changed file-entry-cache constraint (`11.1.5 || >11.1.6 <12`), resolved to 11.1.5; they are not unrelated workspace upgrades. All non-root importer versions remain identical after normalizing the ESLint peer suffix. Existing picomatch/postcss overrides and allowBuilds are unchanged. Rollback: revert this dependency commit and use a frozen install; this restores the vulnerable baseline and is not an acceptable security completion.

## Validation record and final-SHA protocol

Evidence directory in the isolated worktree: `.agent/any-858/` (ignored; tool output, not a personal diary). Experimental one-sided/8.74 locks are preserved outside this checkout at `D:/Devpy/anytoolai-platform/.agent/any-858-candidates/`, so a whole-checkout Trivy scan examines the shipped workspace graph without scanner exclusions. No filtering, severity exclusion, ignore rule or scanning-policy change is used.

The final commit SHA and lockfile SHA-256 are recorded after commit in `final-verification.json` in the evidence directory and in the handoff. A commit cannot include its own SHA; no amendment is made after the final-SHA checks. Every verification command records its starting/ending SHA and lock hash in that receipt. Precommit checks below are preliminary and do not replace final-SHA verification.

- Initial system-Python doctor failed because pytest/yaml were absent. Canonical quick-check bootstrapped .quick-check-venv; `.quick-check-venv/Scripts/python.exe scripts/agent/runner.py doctor` then passed.
- Baseline frozen installation and all workspace lint scripts passed. Initial lint attempted before installation finished failed with missing executable; rerun after installation passed.
- Selected pair's frozen install and complete `corepack pnpm lint` passed before commit. No new lint rules, test skips or suppressions.
- Default shell pnpm is 11.25.0; all resolution used corepack pnpm 10.34.1. Python's Windows subprocess cannot directly launch the .cmd-only pnpm shim. Downloaded official @pnpm/win-x64@10.34.1, verified npm SHA-512 integrity, and placed its executable first on PATH for canonical checks. This is local environment setup, not a repo change.
- Downloaded CI-pinned Trivy 0.76.1 and verified release SHA-256 `1051f49cb22d5284f43425f72aad9cda63ca12ceb92e7caa06903490c82dc9bf`. Fresh DB downloaded 2026-11-27. Preliminary all-severity root lock scan reports no minimatch vulnerability; three Medium findings remain on unchanged Next 15.5.28: CVE-2026-119346/119347/119348, outside the lint dependency graph and outside this fix's scope.
- Full-check and frontend-check are running; definitive results and any blockers are in the final receipt. Additional required container/PostgreSQL gates must be distinguished from local graph/lint proof.

Exact final verification commands (using the verified pnpm executable first on PATH):

```text
pnpm --version
pnpm install --frozen-lockfile
pnpm lint
python scripts/agent/runner.py frontend-check
python scripts/agent/runner.py full-check
python scripts/agent/runner.py validate-docs
python scripts/agent/runner.py generate-docs --check
python scripts/agent/runner.py postgresql-check
python scripts/agent/runner.py atoms-proof
python scripts/agent/runner.py prod-smoke
.agent/any-858/trivy/trivy.exe fs --scanners vuln --include-dev-deps --list-all-pkgs --format json --output .agent/any-858/final-trivy.json .
pnpm why -r minimatch --json
```

## Acceptance and remaining work

| Acceptance criterion | Status |
|---|---|
| Every affected dev chain resolves a fixed version; no >=7 <11.0.1 in root lock | Implemented: all lint consumers 11.0.9; independent 5.1.9 retained. Final receipt rechecks lock/tree. |
| Frozen install and complete lint work | Proven before commit; final-SHA rerun required by this assignment and recorded in receipt. |
| Fresh Trivy lacks CVE-2026-118764 | Proven for the selected root lock before commit; final whole-checkout scan and full lint-subgraph assertions recorded in receipt. GHSA-only records checked separately above. |
| Frontend and relevant repository checks work | Final receipt contains each actual result; no missing check counts as pass. |
| Dependabot #181 closes after merge to main | Pending authorized PR/merge and GitHub rescan; cannot be proven locally. No PR or alert mutation authorized. |

Local remaining limitations: unavailable Docker daemon and missing PostgreSQL maintenance URL prevent container/DB production-semantics proof. Required GitHub statuses still need to run on a future authorized PR and merge. Unrelated Next.js Medium findings remain visible. Recheck advisories when integrating because security data can change.

## Complete path proof

The lockfile snapshot traversal follows dependencies and optional dependencies, including pnpm-materialized peers, stops cycles per path, and starts at every importer dependency kind. Baseline and final each yield 38 simple paths: 35 root dev lint/peer paths, two kernel-demo-ce dev WXT optional-peer paths, and one CE-kit dev generator path. No runtime importer reaches minimatch. Workspace links add no runtime path because CE-kit declares the generator only as devDependency. WXT declares an optional ESLint peer; pnpm materializes it as an optional dependency edge.

Each alias below has its exact baseline and final version. Every path uses those versions; ranges on every edge follow in the table.

| Alias | Package | Baseline | Final |
|---|---|---|---|
| J | `@eslint/js` | 10.0.1 | 10.0.1 |
| E | `eslint` | 10.9.1 | 10.15.0 |
| R | `eslint-plugin-react-hooks` | 7.1.1 | 7.1.1 |
| C | `@eslint/config-array` | 0.23.5 | 0.23.7 |
| T | `typescript-eslint` | 8.69.0 | 8.73.0 |
| G | `@typescript-eslint/eslint-plugin` | 8.69.0 | 8.73.0 |
| P | `@typescript-eslint/parser` | 8.69.0 | 8.73.0 |
| Y | `@typescript-eslint/type-utils` | 8.69.0 | 8.73.0 |
| U | `@typescript-eslint/utils` | 8.69.0 | 8.73.0 |
| S | `@typescript-eslint/typescript-estree` | 8.69.0 | 8.73.0 |
| H | `@eslint-community/eslint-utils` | 4.10.1 | 4.10.1 |
| M | `minimatch` | 10.2.6, 5.1.9 | 11.0.9, 5.1.9 |
| O | `openapi-typescript` | 7.13.0 | 7.13.0 |
| D | `@redocly/openapi-core` | 1.34.21 | 1.34.21 |
| W | `wxt` | 0.21.4 | 0.21.4 |

| Consumer edge | Kind | Baseline declared range → resolved | Final declared range → resolved |
|---|---|---|---|
| J → E | peer | `^10.0.0` → 10.9.1 | `^10.0.0` → 10.15.0 |
| E → H | dependency | `^4.8.0` → 4.10.1 | `^4.8.0` → 4.10.1 |
| E → C | dependency | `^0.23.5` → 0.23.5 | `^0.23.6` → 0.23.7 |
| E → M | dependency | `^10.2.5` → 10.2.6 | `^11.0.5` → 11.0.9 |
| R → E | peer | `^3.0.0 || ^4.0.0 || ^5.0.0 || ^6.0.0 || ^7.0.0 || ^8.0.0-0 || ^9.0.0 || ^10.0.0` → 10.9.1 | `^3.0.0 || ^4.0.0 || ^5.0.0 || ^6.0.0 || ^7.0.0 || ^8.0.0-0 || ^9.0.0 || ^10.0.0` → 10.15.0 |
| C → M | dependency | `^10.2.4` → 10.2.6 | `^11.0.5` → 11.0.9 |
| T → G | dependency | `8.69.0` → 8.69.0 | `8.73.0` → 8.73.0 |
| T → P | dependency | `8.69.0` → 8.69.0 | `8.73.0` → 8.73.0 |
| T → S | dependency | `8.69.0` → 8.69.0 | `8.73.0` → 8.73.0 |
| T → U | dependency | `8.69.0` → 8.69.0 | `8.73.0` → 8.73.0 |
| T → E | peer | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.9.1 | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.15.0 |
| G → Y | dependency | `8.69.0` → 8.69.0 | `8.73.0` → 8.73.0 |
| G → U | dependency | `8.69.0` → 8.69.0 | `8.73.0` → 8.73.0 |
| G → P | peer | `^8.69.0` → 8.69.0 | `^8.73.0` → 8.73.0 |
| G → E | peer | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.9.1 | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.15.0 |
| P → S | dependency | `8.69.0` → 8.69.0 | `8.73.0` → 8.73.0 |
| P → E | peer | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.9.1 | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.15.0 |
| Y → S | dependency | `8.69.0` → 8.69.0 | `8.73.0` → 8.73.0 |
| Y → U | dependency | `8.69.0` → 8.69.0 | `8.73.0` → 8.73.0 |
| Y → E | peer | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.9.1 | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.15.0 |
| U → H | dependency | `^4.9.1` → 4.10.1 | `^4.9.1` → 4.10.1 |
| U → S | dependency | `8.69.0` → 8.69.0 | `8.73.0` → 8.73.0 |
| U → E | peer | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.9.1 | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.15.0 |
| S → M | dependency | `^10.2.2` → 10.2.6 | `^11.0.1` → 11.0.9 |
| H → E | peer | `^6.0.0 || ^7.0.0 || >=8.0.0` → 10.9.1 | `^6.0.0 || ^7.0.0 || >=8.0.0` → 10.15.0 |
| O → D | dependency | `^1.34.6` → 1.34.21 | `^1.34.6` → 1.34.21 |
| D → M | dependency | `5.1.9` → 5.1.9 | `5.1.9` → 5.1.9 |
| W → E | peer | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.9.1 | `^8.57.0 || ^9.0.0 || ^10.0.0` → 10.15.0 |

Importer edges: root dev J `^10.0.1`, E `^10.9.1` → `^10.15.0`, R `^7.1.1`, T `^8.69.0` → `^8.73.0`; CE-kit dev O `^7.13.0`. Resolved versions are in the alias table. Package-internal dependency edges inherit development-only use from these importer edges.

| # | Complete path (root dev unless CE-kit specified) |
|---|---|
| 1 | J → E → C → M |
| 2 | J → E → M |
| 3 | E → C → M |
| 4 | E → M |
| 5 | R → E → C → M |
| 6 | R → E → M |
| 7 | T → G → P → S → M |
| 8 | T → G → P → E → C → M |
| 9 | T → G → P → E → M |
| 10 | T → G → Y → S → M |
| 11 | T → G → Y → U → H → E → C → M |
| 12 | T → G → Y → U → H → E → M |
| 13 | T → G → Y → U → S → M |
| 14 | T → G → Y → U → E → C → M |
| 15 | T → G → Y → U → E → M |
| 16 | T → G → Y → E → C → M |
| 17 | T → G → Y → E → M |
| 18 | T → G → U → H → E → C → M |
| 19 | T → G → U → H → E → M |
| 20 | T → G → U → S → M |
| 21 | T → G → U → E → C → M |
| 22 | T → G → U → E → M |
| 23 | T → G → E → C → M |
| 24 | T → G → E → M |
| 25 | T → P → S → M |
| 26 | T → P → E → C → M |
| 27 | T → P → E → M |
| 28 | T → S → M |
| 29 | T → U → H → E → C → M |
| 30 | T → U → H → E → M |
| 31 | T → U → S → M |
| 32 | T → U → E → C → M |
| 33 | T → U → E → M |
| 34 | T → E → C → M |
| 35 | T → E → M |
| 36 | W → E → C → M |
| 37 | W → E → M |
| 38 | CE-kit dev → O → D → M |

## Host diagnostics before final verification

The selected pair's normal frontend-check reached tests and failed only the existing ce-kit hooks regression test's 5000 ms timeout. A focused diagnostic with a 30000 ms command-line timeout passed the assertion in approximately 5980 ms; that diagnostic is not a passing canonical check. An exact baseline source snapshot (26128baa, frozen install) passed the focused test in 4420 ms on Windows. The performance margin is a remaining Windows validation concern, not dismissed as an established pre-existing failure.

The preliminary full-check was interrupted after repeated backend lock tests failed. A focused fail-fast diagnostic identifies an untrusted write grant on C:/Users/jackd/AppData/Local/Temp, rejected by the repository's production deployment-lock ACL validator. No Windows permissions or security checks were weakened. Existing Ubuntu WSL (Python 3.12.3, uv 0.12.5) is available; final-commit Linux checks will use a native filesystem checkout to avoid the host ACL condition and measure standard frontend tests independently. Windows canonical check failures remain explicitly reported even if Linux passes.
