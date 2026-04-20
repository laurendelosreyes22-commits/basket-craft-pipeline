# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

All commands use `.venv/bin/python` — never the system Python.

Credentials live in `.env` (gitignored). The file has four credential groups:
- `MYSQL_*` — source database at `db.isba.co`
- `PG_*` — local Docker PostgreSQL on port 5433 (used by tests and the original pipeline)
- `RDS_*` — AWS RDS PostgreSQL in `us-east-1` (basket-craft-db)
- `SNOWFLAKE_*` — Snowflake destination (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, `SNOWFLAKE_ROLE` optional)

## Commands

```bash
# Run the full ELT pipeline (MySQL → raw → analytics, targets local Docker Postgres)
.venv/bin/python run_pipeline.py

# Load all raw MySQL tables into AWS RDS (no transforms, all 8 tables)
.venv/bin/python -c "from pipeline.load_raw import load_raw; load_raw()"

# Load all raw tables from RDS into Snowflake basket_craft.raw (truncate-and-reload)
.venv/bin/python -m pipeline.load_snowflake

# Start local Postgres (required for tests and run_pipeline.py)
docker compose up -d

# Initialize schemas in local Postgres (run once after docker compose up)
.venv/bin/python -c "
from sqlalchemy import create_engine, text
from pipeline.config import POSTGRES_URL
from pathlib import Path
engine = create_engine(POSTGRES_URL)
with engine.begin() as conn:
    conn.execute(text(Path('sql/create_schemas.sql').read_text()))
"

# Run all tests (requires Docker Postgres running)
.venv/bin/pytest tests/

# Run a single test
.venv/bin/pytest tests/test_pipeline.py::test_transform_produces_rows
```

## Architecture

This is an ELT pipeline for a Basket Craft e-commerce course project. There are **two separate PostgreSQL targets** — local Docker and AWS RDS — and two separate entry points for loading data.

### Data Flow

```
MySQL (db.isba.co)
  └─ extract.py ──→ raw.* (local Docker, 3 tables: orders, order_items, products)
                       └─ transform.py ──→ analytics.monthly_sales_summary

MySQL (db.isba.co)
  └─ load_raw.py ──→ raw.* (AWS RDS, all 8 tables, no transforms)
                         └─ load_snowflake.py ──→ basket_craft.raw.* (Snowflake, all 8 tables)
```

The MySQL source has 8 tables total: `employees`, `order_item_refunds`, `order_items`, `orders`, `products`, `users`, `website_pageviews`, `website_sessions`.

### Module Responsibilities

| File | Role |
|---|---|
| `run_pipeline.py` | Orchestrates `extract()` → `transform()`; exits 1 on failure |
| `pipeline/extract.py` | Reads 3 MySQL tables with schema drift checks and column renames/defaults, loads into local `raw.*` via pandas `to_sql(if_exists='replace')` |
| `pipeline/load_raw.py` | Auto-discovers all MySQL tables, loads each as-is into RDS `raw.*` |
| `pipeline/load_snowflake.py` | Reads all 8 tables from RDS `raw.*`, truncates and reloads each into Snowflake `basket_craft.raw` via `write_pandas()` with `quote_identifiers=False` |
| `pipeline/transform.py` | Executes `sql/monthly_summary.sql` against PostgreSQL |
| `pipeline/config.py` | Builds `MYSQL_URL`, `POSTGRES_URL` (local Docker), and `RDS_URL` from `.env` |
| `sql/monthly_summary.sql` | TRUNCATE + INSERT aggregation — edit this to change the transform logic |
| `sql/create_schemas.sql` | Idempotent DDL — run once on local setup |

### Key Design Decisions

- **Full refresh strategy**: every run replaces raw tables and truncates analytics. Safe to re-run with no duplicates.
- **`extract.py` has schema drift protection**: it checks that expected columns exist in MySQL before loading; it will fail fast if the source schema changes. `load_raw.py` does no such check — it loads whatever is there.
- **`order_items` in MySQL has no `quantity` column**: each row is one unit. The `conftest.py` fixture has a `quantity` column because the local Postgres schema was designed with it — these schemas diverge from the actual RDS raw schema.
- **Tests target local Docker Postgres** via `POSTGRES_URL`, not RDS. Tests require `docker compose up -d` and initialized schemas first.
- **Transform SQL references `raw.order_items.quantity`** — this works against the local fixture but will fail if run against the RDS raw schema (which reflects actual MySQL columns).
- **Snowflake identifiers are uppercase and unquoted** — `load_snowflake.py` uppercases all DataFrame column names and passes `table_name=table.upper()` with `quote_identifiers=False`. Snowflake receives unquoted uppercase identifiers and stores them as standard uppercase internally. SQL queries (including post-load validation) use lowercase unquoted identifiers; Snowflake normalizes them to uppercase at query time. Never introduce quoted identifiers (`"column_name"`) — this is the #1 cause of dbt failures with Snowflake.

### Cron Schedule

```
0 2 1 * * cd /path/to/basket-craft-pipeline && .venv/bin/python run_pipeline.py 2>> /var/log/basket_craft_pipeline.log
```

## dbt Project

The dbt project lives at `basket_craft/` inside the repo root. All dbt commands must be run from inside that directory.

```bash
cd basket_craft

# Source env vars so profiles.yml can read them (required before any dbt command)
set -a && source ../.env && set +a

# Build all models
../.venv/bin/dbt run

# Run data tests
../.venv/bin/dbt test

# Build and test in one command
../.venv/bin/dbt build

# Generate and serve documentation
../.venv/bin/dbt docs generate
../.venv/bin/dbt docs serve --port 8080
```

### Profiles

`~/.dbt/profiles.yml` lives outside the repo (never committed). It reads all Snowflake credentials via `env_var()` from the shell environment — the `set -a && source ../.env && set +a` step above is required before running any dbt command. The profile name is `basket_craft` and the target schema is `analytics`.

### Models

**Staging** (`basket_craft/models/staging/`) — rename and cast only, no joins or filters:

| Model | Source |
|---|---|
| `stg_orders` | `raw.orders` |
| `stg_order_items` | `raw.order_items` |
| `stg_products` | `raw.products` |
| `stg_customers` | `raw.users` (via `identifier:`) |

**Marts** (`basket_craft/models/marts/`) — business-level tables:

| Model | Grain | Type |
|---|---|---|
| `dim_date` | One row per calendar day (2020–2030) | table |
| `dim_customers` | One row per customer | table |
| `dim_products` | One row per product | table |
| `fct_order_items` | One row per order line item | table |

Staging models are materialized as **views**; mart models are materialized as **tables**. All identifiers are lowercase and unquoted.
