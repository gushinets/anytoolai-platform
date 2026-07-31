# PostgreSQL Handoff Index Migration Fix

## Brief problem description

Revision `0010_handoffs_index_compat` emitted a schema-qualified index name in raw PostgreSQL
`CREATE INDEX` SQL, causing every clean migration to head to fail before PostgreSQL tests ran.

## Root cause

PostgreSQL permits a schema-qualified table in `CREATE INDEX`, but not a schema-qualified index
identifier in that grammar position. The raw SQL used `platform.index_name` rather than the bare
index name.

## Implementation summary

Keep `platform.product_handoffs` schema-qualified while rendering bare index names for create;
retain the schema-qualified `DROP INDEX` identifier, which PostgreSQL accepts. Revision `0010` is
unreleased and is corrected in place.

## Validation results

- Offline Alembic SQL and migration tests are recorded in the execution plan.
- PostgreSQL online migration validation requires the CI maintenance database URL.
