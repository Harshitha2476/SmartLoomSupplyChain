# MySQL setup for Smart Loom

## New project (recommended)

Run **`database/smartloom_full_schema.sql`** — full database from scratch.

See **`database/README.md`** for instructions and demo logins.

## Existing database only

1. Run **`database/upgrade_tier1_tier2.sql`** (if needed for new tables)
2. Run **`database/triggers.sql`** — **required** for orders and stock to work

Without triggers, the app may double-count or skip stock updates.
