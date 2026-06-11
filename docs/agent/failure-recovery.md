# Failure Recovery

When checks fail:

1. Run `scripts/agent/summarize-failures.sh`.
2. Read the exact failing assertion or lint message.
3. Fix the missing capability or broken contract.
4. Re-run the smallest failing check first.
5. Update execution plan progress.

Do not bypass architecture tests. If a boundary test blocks you, the design is likely wrong or docs need a human decision.
