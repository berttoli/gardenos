# Development handoff

## Current structure

- `app/`: operational API, authentication, domain services, and snapshot/lite tools.
- `migrations/`: database schema revisions.
- `frontend-site/app/garden/`: frontend pages, services, shared components, and demo data.
- `assistant-service/`: optional assistant-service source; not started by default.
- `tests/`: synthetic backend tests.
- `frontend-site/tests/`: frontend checks.

PostgreSQL is the operational source of truth. DuckDB is used for portable snapshots
and a separate lite runtime. The frontend communicates with the operational API.

## Delivered integration milestone

A garden-care task now works from selection through completion:

1. Sign in to the operational backend.
2. Load task occurrences using stable backend identifiers.
3. Submit completion through the protected API, showing pending and failure states.
4. Refresh the workspace after a successful write.
5. Reload the page or sign in in a fresh browser context; completion stays visible.

The browser suite exercises this flow against an API with disposable data. CI uses
the exact PostgreSQL image pinned by Compose and applies the real migrations.
Additional cases cover rejected writes, empty queues, repeat completion, CSRF,
read-only users, explicit nursery scopes, duplicate titles, and API restarts.

Task actions use canonical backend records. Other screens still contain synthetic
demonstration data and need separate integration work.

## Limits and follow-up work

- The supplied frontend is a prototype with additional demonstration screens.
- Offline mutation queues, conflict handling, and background synchronization are
  not established by the lite runtime or connectivity indicators.
- PostgreSQL migration and browser-persistence checks cover this milestone; they do
  not establish backup recovery, load capacity, or every platform workflow.
- Task and workspace access use explicit scope bindings. Other API endpoints have
  not received a comprehensive tenant-isolation audit. Keep this development
  prototype within a trusted local installation pending broader review.
- Deployment, backups, credentials, and operational monitoring require installation-
  specific configuration. This repository contains no existing installation data.
- Review and record actual test results when completing an integration milestone;
  this document is not a claim that every route or platform has been verified.

## Public-source hygiene

Keep test identities and examples synthetic. Use reserved example hostnames in
fixtures, and inject credentials at runtime. Do not add databases, uploads,
generated reports, hosting metadata, copied chat histories, or private operator
notes. Avoid copying Git histories from unrelated or private workspaces.

## Dependency maintenance

Python dependencies are installed from `uv.lock`; frontend dependencies are locked
in `package-lock.json`. Vite is on the patched 8.3 line. The frontend has two
narrow development-tool overrides for patched `minimatch` and `brace-expansion`
versions. Remove them when upstream TypeScript ESLint/ESLint dependency ranges
include the fixes, then run lint, type checks, rendered tests, and browser tests.
They are not browser runtime dependencies.
