# Session 2026-11-15_01 — S1-01 Agency and User models

- **Date/time:** 2026-11-15 (local)
- **Tool / model:** claude, claude-sonnet-5-5
- **Branch / commit base:** sprint-1/database-multitenant-foundation (nothing committed yet)
- **User goal:** "yes your answers are on point, keep working" — approve Threat_Model decisions, start Sprint 1 (S1-01), teach each step.

## Context read at start
Mandatory/README, DECISIONS (D-001..D-010), docs/Threat_Model.md, SaaS_Master_Plan S1-01/S1-02, app/models.py, app/database.py, alembic/env.py.

## Actions log
- Recorded D-011..D-017 in DECISIONS.md (D-017 provisional).
- Added Agency and User models to app/models.py (UUID PKs, role CHECK constraints, lowercase email/slug CHECKs, customer-must-have-agency CHECK). agency_id on users is nullable only for platform staff.
- Added app/services/accounts.py: normalize_email, slugify, AccountError, register_agency_with_owner (atomic, takes no role argument, takes an already-hashed password).
- Added alembic/versions/a1c5e0b7d301_add_agencies_and_users.py (hand-written: Docker was not running, so autogenerate had no DB). Does not touch projects or any existing table.
- Added tests/test_accounts.py (23 tests, in-memory SQLite).

## Files changed
| Path | Change | Summary |
|---|---|---|
| app/models.py | edit | imports (uuid, CheckConstraint, Uuid); Agency, User, PLATFORM_ROLES, AGENCY_ROLES |
| app/services/accounts.py | add | registration rules |
| alembic/versions/a1c5e0b7d301_add_agencies_and_users.py | add | creates agencies, users, ix_users_agency_id |
| tests/test_accounts.py | add | 23 tests |
| Mandatory/DECISIONS.md | edit | D-011..D-017 |

## Verification
- tests/test_accounts.py: 23 passed. Full suite: 1335 passed (1312 + 23), 1 pre-existing warning.
- Alembic on a throwaway SQLite file: upgrade head OK, `alembic check` reports no drift, downgrade -1 OK.
- NOT yet run against Postgres: Docker Desktop was not running. Run `python -m alembic upgrade head` on the dev DB and a scratch DB when it is up.

## Open items / handoff
- S1-01 still to do: dev-only bootstrap for the first platform admin (needs Argon2 hashing from S1-02, argon2-cffi is not installed yet); Postgres run of the migration.
- Nothing committed.
