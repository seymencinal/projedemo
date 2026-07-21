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
