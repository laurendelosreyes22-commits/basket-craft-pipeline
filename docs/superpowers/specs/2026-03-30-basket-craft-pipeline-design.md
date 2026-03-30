# Basket Craft Pipeline — Design Spec

**Date:** 2026-03-30
**Project:** ISBA 4715 — Monthly Sales Dashboard

---

## 1. Overview

A monthly ELT pipeline that extracts raw sales data from the Basket Craft MySQL course database, loads it into a PostgreSQL `raw` schema using pandas, then transforms it with SQL into `analytics.monthly_sales_summary`. Runs automatically via cron with a full refresh on every run.

---

## 2. Pipeline Diagram

```
MySQL (db.isba.co)                      PostgreSQL (Docker — basket_craft_pg)
┌──────────────────────┐                ┌─────────────────────────────────────────────┐
│  orders              │  SQLAlchemy    │  raw schema (mirror)                        │
│  order_items         │──→ extract.py ─│→ raw.orders                                 │
│  products            │  full reads +  │→ raw.order_items  ──→ transform.py ─────────│→ analytics.monthly_sales_summary
└──────────────────────┘  pandas to_sql │→ raw.products         SQL in PG             │
                                        └─────────────────────────────────────────────┘
         ↑                                               ↑
  Course DB credentials                      New Docker container
  (.env — gitignored)                        (docker-compose.yml)

Pattern:   ELT — Extract raw → Load to raw schema → Transform in PG
Scheduler: cron → run_pipeline.py on 1st of each month
Strategy:  full refresh (replace raw tables + truncate analytics on every run)
Tech:      SQLAlchemy + PyMySQL (read) | pandas to_sql (load) | SQLAlchemy (transform)
```

**Data flow:**
1. Cron triggers `run_pipeline.py`
2. `pipeline/extract.py` validates MySQL source columns (schema drift check), then reads all rows via SQLAlchemy → loads into `raw.*` via pandas `to_sql(if_exists='replace')`
3. `pipeline/transform.py` executes `sql/monthly_summary.sql` against PostgreSQL → writes aggregated rows to `analytics.monthly_sales_summary`
4. Exit code 0 on success, 1 on any failure

---

## 3. File Structure

```
basket-craft-pipeline/
├── run_pipeline.py          # Entry point — calls extract then transform
├── pipeline/
│   ├── extract.py           # MySQL → raw.* (schema check + SQLAlchemy read + pandas to_sql)
│   ├── transform.py         # raw.* → analytics.monthly_sales_summary (SQL in PG)
│   └── config.py            # DB connection strings from .env
├── sql/
│   ├── create_schemas.sql   # Idempotent DDL — raw + analytics schemas and tables
│   └── monthly_summary.sql  # TRUNCATE analytics + INSERT aggregated rows
├── docker-compose.yml       # PostgreSQL 16 container (basket_craft_pg)
├── .env                     # Real credentials — gitignored
├── .env.example             # Credential template — committed to git
├── requirements.txt         # Python dependencies
└── tests/
    ├── conftest.py          # Postgres fixtures
    └── test_pipeline.py     # Unit + smoke tests
```

### Script responsibilities

| File | Responsibility |
|------|----------------|
| `run_pipeline.py` | Orchestrates extract → transform; logs result; `sys.exit(1)` on failure |
| `pipeline/extract.py` | Validates MySQL source columns; reads tables; loads into `raw.*` via pandas |
| `pipeline/transform.py` | Executes `sql/monthly_summary.sql` against PostgreSQL |
| `pipeline/config.py` | Loads `.env`; builds SQLAlchemy connection strings for MySQL and PostgreSQL |
| `sql/create_schemas.sql` | Run once on setup — creates all schemas and tables |
| `sql/monthly_summary.sql` | TRUNCATE + INSERT transform query — editable without touching Python |

---

## 4. Table Schemas

### PostgreSQL — `raw` schema (staging mirrors)

```sql
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.orders (
    order_id     INTEGER,
    customer_id  INTEGER,
    order_date   DATE,
    status       TEXT
);

CREATE TABLE IF NOT EXISTS raw.order_items (
    order_item_id  INTEGER,
    order_id       INTEGER,
    product_id     INTEGER,
    quantity       INTEGER,
    price_usd      NUMERIC
);

CREATE TABLE IF NOT EXISTS raw.products (
    product_id    INTEGER,
    product_name  TEXT,
    category_id   INTEGER
);
```

### PostgreSQL — `analytics` schema (output)

```sql
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.monthly_sales_summary (
    month             DATE        NOT NULL,
    product_name      VARCHAR     NOT NULL,
    total_revenue     DECIMAL     NOT NULL,
    order_count       INTEGER     NOT NULL,
    avg_order_value   DECIMAL     NOT NULL,
    total_items_sold  INTEGER     NOT NULL,
    loaded_at         TIMESTAMP   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (month, product_name)
);
```

> `product_name` serves as the category — there is no separate `categories` table in the source DB.

> `loaded_at` records when the pipeline last ran — lets dashboards show data freshness.

> The composite primary key `(month, product_name)` prevents duplicate rows if the pipeline runs more than once in a month.

---

## 5. Transform SQL

**`sql/monthly_summary.sql`** — runs inside PostgreSQL against `raw.*` tables:

```sql
TRUNCATE analytics.monthly_sales_summary;

INSERT INTO analytics.monthly_sales_summary
    (month, product_name, total_revenue, order_count, avg_order_value, total_items_sold, loaded_at)
SELECT
    DATE_TRUNC('month', o.order_date)::DATE         AS month,
    p.product_name                                   AS product_name,
    SUM(oi.quantity * oi.price_usd)                 AS total_revenue,
    COUNT(DISTINCT o.order_id)                       AS order_count,
    SUM(oi.quantity * oi.price_usd)
        / COUNT(DISTINCT o.order_id)                 AS avg_order_value,
    SUM(oi.quantity)                                 AS total_items_sold,
    NOW()                                            AS loaded_at
FROM raw.orders o
JOIN raw.order_items oi ON o.order_id    = oi.order_id
JOIN raw.products    p  ON oi.product_id = p.product_id
GROUP BY
    DATE_TRUNC('month', o.order_date)::DATE,
    p.product_name
ORDER BY
    month,
    product_name;
```

**Assumptions:**
- `price_usd` is a unit price; `total_revenue` = `quantity × price_usd`
- Gross revenue only — no refund adjustments
- No cancelled-order filter (add `WHERE o.status != 'cancelled'` once status values are confirmed)

---

## 6. Infrastructure

### Docker Compose

A single `docker-compose.yml` that runs PostgreSQL. Credentials are read from `.env`.

- Postgres image: `postgres:16`
- Exposed port: `5433` (maps to `5432` inside the container — avoids conflicts with any existing local Postgres)
- Persistent volume for data
- Environment variables for `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

### Environment Variables (`.env`)

The `.env` file holds credentials for both databases:

- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` — source connection
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — destination connection

`.env` is gitignored. `.env.example` (committed) provides the template with keys but no values.

---

## 7. Error Handling

- **Connection failures:** Log the error and exit with a non-zero code. No automatic retries — re-run manually.
- **Schema drift:** Before loading, verify that expected source columns exist in the MySQL tables. Fail fast with a clear message if the schema has changed.
- **Idempotent loads:** Each run truncates `raw` tables and rebuilds `analytics.monthly_sales_summary` from scratch. Safe to re-run without risk of duplicates or partial state.

**Cron entry:**
```
0 2 1 * * cd /path/to/basket-craft-pipeline && python run_pipeline.py 2>> /var/log/basket_craft_pipeline.log
```

---

## 8. Testing

- **Framework:** pytest
- **Unit tests:** Load a small fixture dataset into the Dockerized Postgres `raw` schema, run the transform SQL, and verify the summary table has correct aggregations.
- **Smoke test:** End-to-end run that extracts a small sample from MySQL, loads into Postgres, and verifies the summary table has expected columns and non-null values.
- **Test infrastructure:** Uses the same Docker Postgres instance as the pipeline.

Test files:
- `tests/conftest.py` — Postgres fixtures
- `tests/test_pipeline.py` — Unit + smoke tests

---

## 9. Out of Scope

- Incremental / append-only loads (full refresh is sufficient for ~32K rows)
- Orchestration frameworks (Prefect, Dagster, Airflow) — pure Python + cron is enough at this scale
- Data quality checks beyond schema drift detection
- Dashboard / visualization layer (separate concern)

---

## 10. Dependencies (`requirements.txt`)

```
sqlalchemy
pymysql
psycopg2-binary
pandas
python-dotenv
pytest
```
