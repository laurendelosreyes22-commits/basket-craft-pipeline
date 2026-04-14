# Basket Craft Pipeline

An ELT pipeline for the Basket Craft e-commerce dataset. Extracts raw sales data from a MySQL source database, loads it into PostgreSQL, and transforms it into a monthly sales summary for analytics.

## Infrastructure

| Component | Details |
|---|---|
| Source | MySQL at `db.isba.co` — 8 tables of e-commerce data |
| Local Postgres | Docker container on port `5433` — used for pipeline development and tests |
| AWS RDS | PostgreSQL on `us-east-1` (`basket-craft-db`) — all 8 raw tables loaded as-is |

### AWS RDS

The RDS instance (`basket-craft-db.c6jssyc2m1yr.us-east-1.rds.amazonaws.com`) holds a `raw` schema with a full mirror of the MySQL source:

| Table | Rows |
|---|---|
| `raw.website_pageviews` | 1,188,124 |
| `raw.website_sessions` | 472,871 |
| `raw.order_items` | 40,025 |
| `raw.orders` | 32,313 |
| `raw.users` | 31,696 |
| `raw.order_item_refunds` | 1,731 |
| `raw.employees` | 20 |
| `raw.products` | 4 |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in credentials
```

## Running the Pipeline

**Full ELT pipeline** (MySQL → local Docker Postgres `raw.*` → `analytics.monthly_sales_summary`):
```bash
docker compose up -d
.venv/bin/python run_pipeline.py
```

**Load all raw tables into AWS RDS** (no transforms):
```bash
.venv/bin/python -c "from pipeline.load_raw import load_raw; load_raw()"
```

## Testing

Tests run against the local Docker Postgres instance:
```bash
docker compose up -d
.venv/bin/pytest tests/
```

## Pipeline Architecture

```
MySQL (db.isba.co)
  ├─ extract.py ──→ raw.{orders, order_items, products} (local Docker)
  │                    └─ transform.py ──→ analytics.monthly_sales_summary
  │
  └─ load_raw.py ──→ raw.* (AWS RDS, all 8 tables)
```

The transform step aggregates revenue, order count, average order value, and items sold by month and product into `analytics.monthly_sales_summary`. The SQL is in `sql/monthly_summary.sql` and can be edited without touching Python.

Scheduled via cron on the 1st of each month.
