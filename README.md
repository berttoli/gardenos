# GardenOS

[![GardenOS checks](https://github.com/berttoli/gardenos/actions/workflows/test.yml/badge.svg)](https://github.com/berttoli/gardenos/actions/workflows/test.yml)

GardenOS is a self-hosted garden-management prototype. It combines a Python
FastAPI backend, PostgreSQL operational storage, DuckDB snapshot/lite utilities,
and a React and TypeScript interface built with Vite.

The source includes plant records, observations, care tasks, session authentication,
workspace summaries, and monitoring APIs. The interface also contains clearly
synthetic demonstration data. Some screens illustrate intended workflows; their
presence does not mean every control is connected to the backend.

## Start a local development instance

Prerequisites: Docker with Compose. The supplied stack publishes the frontend and
API on the local machine only.

1. Copy `.env.example` to `.env`.
2. Generate three independent random values for `SECRET_KEY`, `ADMIN_PASSWORD`,
   and `POSTGRES_PASSWORD`. For each value, a command such as
   `python3 -c 'import secrets; print(secrets.token_hex(32))'` produces a suitable
   local development value. Keep those values in the ignored `.env` file.
3. Run `docker compose up --build`.
4. Open the frontend at `http://127.0.0.1:3000` and API documentation at
   `http://127.0.0.1:8000/docs`. Use the username and password from your local
   configuration to sign in.

Compose starts PostgreSQL and gives the backend its connection URL. Startup applies
the database migrations and initializes the configured administrator. Existing
database volumes retain their data when containers restart. This development
configuration is not a public Internet deployment configuration.
The Compose project is named `gardenos-dev` so the fresh checkout has its own
named volumes. Stop any existing app using ports 3000/8000 before starting it.
Existing installation data is not imported automatically. The exact database image
and update procedure are recorded in [the database guide](docs/DATABASE.md).

No shared application password or signing key is built into the application.
The operational backend refuses to start without `SECRET_KEY`, `ADMIN_PASSWORD`,
and `DATABASE_URL`. Compose also requires `POSTGRES_PASSWORD`.

## Develop without containers

The backend requires Python 3.13 or later and a local PostgreSQL database. Install
dependencies with `uv sync --extra dev`, then supply the required environment
variables in your shell. The application does not automatically load `.env` files
outside Compose.

```sh
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The frontend requires Node.js 22.13 or later:

```sh
cd frontend-site
npm ci
VITE_GARDENOS_API_BASE_URL=http://127.0.0.1:8000/api/v1 npm run dev -- --host 127.0.0.1 --port 3000
```

The frontend builds to static files with Vite. It does not require a hosting
account, server rendering, cloud database binding, or platform-injected authentication
headers. React, TypeScript, and Vite keep the browser application separate from
the existing FastAPI and PostgreSQL backend.

## Verification

```sh
uv run pytest tests assistant-service/tests
uv run ruff check app tests scripts migrations
cd frontend-site
npm test
npm run lint
npm run typecheck
npx playwright install chromium
VITE_GARDENOS_API_BASE_URL=http://127.0.0.1:8138/api/v1 npm run build
GARDENOS_E2E_PYTHON=.venv/bin/python npm run test:e2e
```

Backend tests use synthetic SQLite fixtures, including a file-backed application
restart test. Browser tests start an isolated API and verify task completion,
reload, fresh sign-in, retry, failure, and empty-queue behavior. The default local
browser database is temporary SQLite. CI runs those browser tests against the
same pinned PostgreSQL image as Compose, applying the real migrations first.
No repository secrets or existing installation data are used by CI.

To run the PostgreSQL browser variant locally, supply
`GARDENOS_E2E_DATABASE_URL` for an **empty** loopback database named
`gardenos_e2e_test`. The runner rejects other database names, remote hosts,
query overrides, and nonempty databases. It never clears an existing database.
See [the development handoff](docs/HANDOFF.md) and
[archived decisions](docs/DECISIONS.md) for remaining scope.

## Repository boundaries

This repository contains selected application source and synthetic tests. It does
not include an existing installation's databases, uploads, reports, backup archives,
hosting identifiers, credentials, internal network configuration, or development
history. The public SVG illustrations are original geometric demo artwork.

Store runtime data outside Git. The ignore rules exclude common database, export,
environment, cache, and test-output paths. Review staged changes before publishing
new files; ignore rules cannot identify personal data embedded in source text.

Licensed under the [MIT License](LICENSE).
