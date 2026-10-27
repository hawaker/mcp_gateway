# GenBI: Wren / ibis deploy notes

Optional Docker sidecars for semantic SQL (Wren Engine) and connector execution (ibis).  
**Vector indexes stay on the existing application PostgreSQL (pgvector).** This stack does **not** add a second vector database (no Qdrant / Milvus / extra Postgres).

## Prerequisites

1. Application DB is **PostgreSQL** (`DATABASE_TYPE=postgres` in `backend/env/.env.*`).
2. On that same instance:

   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

3. Leave `GENBI_VECTOR_*` empty so the backend reuses `DATABASE_*` (see `backend/env/.env.example`). Only set `GENBI_VECTOR_DATABASE_URL` / `GENBI_VECTOR_PG_*` if you must override — still point at **the same** Postgres, not a new service.

## Start Wren + ibis

```bash
cd deploy/genbi
cp .env.example .env
docker compose --env-file .env up -d
```

Default localhost ports:

| Service        | Host port | Env for FastAPI backend              |
|----------------|-----------|--------------------------------------|
| Wren Engine    | 8080      | `GENBI_WREN_ENGINE_ENDPOINT`         |
| ibis server    | 18000     | `GENBI_IBIS_ENDPOINT`                |

`18000` avoids colliding with the FastAPI app on `8001`.

Backend example:

```env
DATABASE_TYPE = postgres
DATABASE_HOST = localhost
DATABASE_PORT = 5432
# …

GENBI_IBIS_ENDPOINT = http://127.0.0.1:18000
GENBI_WREN_ENGINE_ENDPOINT = http://127.0.0.1:8080
# GENBI_VECTOR_* intentionally unset → same Postgres + pgvector
```

## What this compose does *not* include

- No `qdrant` / `milvus` / second `postgres` service for vectors
- No change to `docker/docker-compose.yaml` MySQL stack — GenBI metadata requires Postgres (external or your own PG compose); use the same PG for vectors

## Relate to main deploy

- App containers: `docker/` + root `DEPLOYMENT.md`
- GenBI engines only: this directory
- Oracle thick client ibis image (optional): see tiga-case `deploy/genbi/ibis-oracle` if you need that connector build
