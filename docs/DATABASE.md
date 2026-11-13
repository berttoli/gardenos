# PostgreSQL runtime

Compose and browser-persistence CI use the same public Docker Official Image:

```text
postgres:16.16-alpine3.23@sha256:48340c4811085e083751cab526e533662da19585c1e6942a28b9c48ce7fcb8b2
```

The digest pins the multi-platform image index, allowing the same reference on
ARM64 development machines and AMD64 CI. It was resolved from the official
registry on November 12, 2026. This is a reusable PostgreSQL 16 baseline; no custom
image, private registry, extension bundle, or connection pool is required.
The API container installs PostgreSQL 16 client utilities from the signed PGDG
repository so its backup commands use the same server major version.

The database volume is mounted at `/var/lib/postgresql/data`, the persistence path
for this image. GardenOS owns its database and migrations. Sharing a version with
other applications does not mean sharing credentials, schemas, or data volumes.

## Updating the pin

Update the exact tag and index digest together in `compose.yaml` and
`.github/workflows/test.yml`. Run migrations and browser persistence tests against
the candidate image. Review release notes and verify backup/restore before
updating an existing installation. The dependency-update workflow proposes image
updates for review; it does not automatically deploy or merge them.

Do not point a different PostgreSQL major version at an existing data directory.
A major upgrade requires a planned `pg_upgrade` or dump/restore procedure. The
public checkout contains no existing database and performs no data migration from
another installation.

Sources: [Docker Official Image documentation](https://hub.docker.com/_/postgres),
[PostgreSQL version policy](https://www.postgresql.org/support/versioning/), and
[16.16 release announcement](https://www.postgresql.org/about/news/postgresql-187-1712-1616-1520-1425-and-19-rc-2-released-3442/).
