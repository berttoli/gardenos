# Architecture and project history

This is a curated archive of implementation decisions. It contains no chat
transcripts, personal workspace paths, installation records, or production data.

## Runtime

The web application uses React, TypeScript, and Vite. Its existing screens and
theme system are retained. The generated Next-compatible hosting layer and unused
Cloudflare integration were removed because this application only needs a static
web client for its operational API.

FastAPI and SQLAlchemy remain the backend. Rewriting the domain services in another
language would delay the useful workflow without improving task persistence.
A native desktop wrapper is a possible future client, not a current dependency.

PostgreSQL owns operational state. DuckDB supports snapshots, analytics, and the
separate lite runtime. It does not implement an offline mutation queue or automatic
conflict resolution.

## API and task completion

The authenticated HTTP/JSON API under `/api/v1` is the frontend contract. The v2
protocol is incremental and does not replace that contract.

Task occurrences have stable identifiers. Completion requires task-write access,
an accessible scope, and CSRF protection for cookie-authenticated requests. A
successful write commits its completion timestamp and event before the frontend
refreshes the canonical workspace. Repeating a completion preserves the original
record. Skipped occurrences cannot be completed.

Pending and completed queues come from the backend. An empty or unavailable task
queue does not become a demonstration queue. Completed history includes the newest
50 accessible records; pending buckets also have a 50-record limit. Pagination and
full-history reporting remain future work.

Scoped access uses explicit identifiers. Legacy location records must be bound
through a scope node's `metadata_json.source_location_id`. Names and slugs never
grant access; missing or ambiguous bindings are invisible to scoped users.
Workspace navigation and plant counts follow the same explicit bindings.

## Public handoff boundary

This repository begins with a reviewed source import and fresh Git history.
Existing installation data, uploads, database files, infrastructure overrides,
hosting metadata, research output, and private design references are excluded.
Illustrative assets and test fixtures are synthetic.

The delivered milestone is task completion and reload persistence. Other screens
retain prototype or demonstration behavior; their presence is not a claim of a
complete production workflow. Background execution, synchronization, and broad
platform hardening need separate implementation and verification.

GardenOS has no Carbon compiler implementation or runtime dependency. No shared
Carbon repository or umbrella rename is required.
