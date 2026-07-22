# AI Market Intelligence Platform

## Production configuration

The backend reads configuration from environment variables and, for local development only,
from `backend/.env`. Copy `backend/.env.example` to `backend/.env` and replace placeholder
values without committing the resulting file.

`ENVIRONMENT` accepts `local`, `test`, `staging`, or `production`. In `staging` and
`production`, `DATABASE_USER` and `DATABASE_PASSWORD` are required; startup fails when either
is missing. Local and test environments retain explicit `postgres` defaults only when those
variables are absent.

Required database variables outside local and test:

- `DATABASE_USER`
- `DATABASE_PASSWORD`

Database connection variables with local defaults:

- `DATABASE_HOST`
- `DATABASE_PORT`
- `DATABASE_NAME`

Optional pool variables:

- `DATABASE_POOL_SIZE`
- `DATABASE_MAX_OVERFLOW`
- `DATABASE_POOL_TIMEOUT`
- `DATABASE_POOL_RECYCLE`

## Health endpoints

- `GET /health` is a liveness check. It returns `{"status": "ok"}` and does not access external dependencies.
- `GET /ready` is a readiness check. It performs a minimal PostgreSQL query and returns `503 Service Unavailable` without exposing internal database details if the database is unavailable.

## Identity and tenancy foundation

Every company belongs to exactly one organization. Organization slugs and user emails are
normalized before persistence. A user can belong to an organization once, with one of the
following stored roles: `owner`, `admin`, `member`, or `viewer`. This release establishes the
domain model only; it does not implement authentication or authorization.

Until authentication is implemented, Company API requests must supply an `X-Organization-ID`
UUID header. This is a temporary development-only context mechanism, **not a security
boundary**. Production deployment must not treat the header as proof of identity; a future
authentication layer must derive the organization context from verified credentials.

The tenancy migration creates organizations, users, memberships, the `membership_role` PostgreSQL
enum, and `companies.organization_id`. Existing company rows are retained and assigned to the
deterministic `legacy-bootstrap` organization (`00000000-0000-0000-0000-000000000001`) before
the ownership column becomes non-nullable. New company uniqueness is scoped to organization,
exchange, and ticker.

## Research, Datasource, and Import Job foundation

`Research` is a tenant-owned analysis workspace (`draft`, `active`, or `archived`). Its API is
`POST/GET /researches`, `GET/PATCH/DELETE /researches/{research_id}`. A `Datasource` belongs to
both an organization and a research, preserves object-shaped JSON configuration, and has source
types `csv`, `excel`, `url`, and `manual`; its endpoints are `POST/GET
/researches/{research_id}/datasources` and `GET/PATCH/DELETE /datasources/{datasource_id}`.

An `Import Job` belongs to one organization, research, and datasource. Its endpoints are
`POST/GET /datasources/{datasource_id}/import-jobs`, `GET /import-jobs/{import_job_id}`, and
`PATCH /import-jobs/{import_job_id}/status`. Its permitted lifecycle transitions are:

- `pending` → `running` or `cancelled`
- `running` → `completed`, `failed`, or `cancelled`

Moving to `running` sets `started_at`. Any terminal state sets `completed_at`; cancellation from
pending leaves `started_at` empty, while cancellation from running preserves it. Completion clears
the error message; failure requires a non-empty error message.

Counters are non-negative, cannot decrease, and `processed_items + failed_items` cannot exceed
`total_items`; completion additionally requires that sum to equal `total_items`. Idempotency is
scoped to `organization_id + datasource_id + idempotency_key`, so the same key is allowed for a
different datasource. PostgreSQL enforces the datasource composite relationship
`(datasource_id, organization_id, research_id)` and rejects inconsistent tenant/research links.

All queries are organization-scoped. `X-Organization-ID` remains a development-only tenant context
mechanism and is not authentication or a security boundary. File upload, CSV/Excel parsing, URL
crawling, workers, Redis, Celery, AI, and background ingestion execution are not implemented yet.
