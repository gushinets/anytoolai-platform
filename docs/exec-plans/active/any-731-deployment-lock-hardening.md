# Execution Plan: Deployment lock hardening

## Status

- State: active
- Owner: agent
- Created: 2026-11-02
- Last updated: 2026-11-02
- Review date: 2026-11-02
- Next action: Confirm Windows and complete full-check in CI
- Blocker: Local baseline requires passwordless sudo for an existing activation-marker test

## Goal and scope

Protect prod and Atom Lab deployment locks against local file substitution while retaining
cross-checkout process exclusion and automatic release on exit. No dependencies or API changes.

## Implementation steps

- Use a fixed private user-profile directory, independent of checkout and temporary directories.
- Reject unsafe directories and files; open POSIX files without following links and validate descriptors.
- Preserve flock/msvcrt locking and distinguish open failures from lock contention.
- Test substitution, permissions, cross-checkout contention and crash recovery; document migration.

## Decision log

- User confirmed that all deployments run as one system user. Cross-user locking is out of scope.
- Windows uses LOCALAPPDATA and profile ACLs; reject reparse points. POSIX checks ownership and modes.
- Never unlink lock files: existing holders must continue to coordinate through the same inode.

## Validation

- Targeted runner lock/concurrency tests: 27 passed on Linux, including a separate runner copy
  in another checkout, normal exit and forced process termination for both Compose projects.
- Final quick-check: 2938 passed, 1 failed, 486 deselected. The sole failure is the existing
  activation-marker test requiring passwordless sudo to run as nobody; this environment requests
  interactive authentication. Config, architecture, docs and generated-doc checks passed.
- Managed Python 3.12 doctor and git diff whitespace checks passed.
- An earlier full-check stopped in baseline with intermediate directory-validation failures;
  those lock failures were corrected and cleared by the final baseline. Full-check is not green;
  frontend stages were not reached. Windows and actual Docker deployment remain for CI.
- Ruff has existing findings in these files; no new findings in the added code.

## Progress log

- Implemented persistent private profile directories and safe lock-file validation for both callers.
- Newly created intermediate directories also use 0700, independent of permissive umask.
- Validate POSIX ancestors through the user-profile boundary; reject symlinks and writable ancestors.
- Split unsafe-open errors from contention, retain persistent inodes and OS process locking.
- Updated operator instructions with single-user scope, permissions and old-runner migration.
- Baseline limitation above remains visible; no unrelated test or permission changes were made.

## Review fixes (2026-11-02)

Both security findings verified against current code and PR inline comments/replies read.
Removed the sticky-bit exception and now require trusted POSIX owners through the profile boundary.
Check each directory from the profile downward before creating descendants; reject intermediate
reparse points on Windows. Windows system PowerShell inspects owner SIDs and DACL grants for
all directories and existing lock files; failures block deployment. No dependencies added.
Added live-holder directory-replacement regressions with modeled foreign ownership, real Windows
ACL/junction tests, and platform-independent fail-closed inspection tests.
Targeted validation: 35 passed, 4 Windows-only tests skipped on Linux. Complete runner suite
has only the existing activation-marker failure requiring passwordless sudo. Documentation,
architecture and whitespace checks pass; no new Ruff findings in added code. Windows execution
and Docker smoke remain unverified locally. Isolated Windows test profiles receive private ACLs
so tests do not rely on permissive CI workspace inheritance. Existing Compose-error mocks now
allow real ACL inspection instead of intercepting PowerShell calls.
