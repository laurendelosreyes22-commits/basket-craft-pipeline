# Basket Craft Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a monthly ELT pipeline that extracts raw sales data from MySQL, stages it in PostgreSQL, and aggregates it into `analytics.monthly_sales_summary`.

**Architecture:** Extract raw tables from MySQL into a `raw` PostgreSQL schema using pandas `to_sql`, then execute a pure-SQL transform inside PostgreSQL to produce the analytics summary. Full refresh on every run — no incremental logic needed at ~32K rows.

**Tech Stack:** Python 3 (venv), SQLAlchemy, PyMySQL, pandas, psycopg2-binary, python-dotenv, pytest, Docker / docker-compose

---

## File Map

| File | Create / Modify | Purpose |
|------|----------------|---------|
| `requirements.txt` | Create | Pin all dependencies |
| `.env.example` | Create | Credential template (committed) |
| `docker-compose.yml` | Create | PostgreSQL 16 container |
| `pipeline/__init__.py` | Create | Makes `pipeline/` a Python package |
| `pipeline/config.py` | Create | SQLAlchemy URLs from `.env` |
| `sql/create_schemas.sql` | Create | Idempotent DDL for raw + analytics schemas |
| `sql/monthly_summary.sql` | Create | TRUNCATE + INSERT transform query |
| `tests/conftest.py` | Create | pytest fixture: PG engine + raw fixture data |
| `tests/test_pipeline.py` | Create | Unit tests (transform SQL) + smoke test (end-to-end) |
| `pipeline/transform.py` | Create | Executes `monthly_summary.sql` against PG |
| `pipeline/extract.py` | Create | Schema drift check + MySQL → raw.* via pandas |
| `run_pipeline.py` | Create | Entry point: extract → transform, exit 1 on error |
| `.env` | Modify | Add `POSTGRES_*` keys alongside existing `MYSQL_*` keys |

---

## Task 1: Virtual environment and dependencies

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Create the virtual environment**

```bash
cd /Users/laurendelosreyes/isba-4715/basket-craft-pipeline
python3 -m venv .venv
source .venv/bin/activate
```

- [ ] **Step 2: Create `requirements.txt`**

```
sqlalchemy==2.0.36
pymysql==1.1.1
psycopg2-binary==2.9.10
pandas==2.2.3
python-dotenv==1.0.1
pytest==8.3.4
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add requirements.txt"
```

---

## Task 2: Docker Compose and `.env` setup

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Modify: `.env`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    container_name: basket_craft_pg
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5433:5432"
    volumes:
      - basket_craft_pg_data:/var/lib/postgresql/data

volumes:
  basket_craft_pg_data:
```

- [ ] **Step 2: Create `.env.example`**

```
MYSQL_HOST=db.isba.co
MYSQL_PORT=3306
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DATABASE=basket_craft

POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=basket_craft
POSTGRES_USER=
POSTGRES_PASSWORD=
```

- [ ] **Step 3: Add PostgreSQL keys to `.env`**

Open `.env` and append these lines (fill in values you choose for the local container):

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=basket_craft
POSTGRES_USER=pipeline
POSTGRES_PASSWORD=pipeline_pass
```

- [ ] **Step 4: Start the container**

```bash
docker compose up -d
```

Expected output includes `Container basket_craft_pg  Started`.

- [ ] **Step 5: Verify the container is running**

```bash
docker ps --filter name=basket_craft_pg
```

Expected: one running container on port `5433`.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: add docker-compose and env template"
```

---

## Task 3: Config module

**Files:**
- Create: `pipeline/__init__.py`
- Create: `pipeline/config.py`

- [ ] **Step 1: Create `pipeline/__init__.py`**

```python
```

(Empty file — makes `pipeline/` importable as a package.)

- [ ] **Step 2: Create `pipeline/config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_URL = (
    "mysql+pymysql://{user}:{password}@{host}:{port}/{db}".format(
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        host=os.environ["MYSQL_HOST"],
        port=os.environ["MYSQL_PORT"],
        db=os.environ["MYSQL_DATABASE"],
    )
)

POSTGRES_URL = (
    "postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}".format(
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        db=os.environ["POSTGRES_DB"],
    )
)
```

- [ ] **Step 3: Verify config loads without error**

```bash
python -c "from pipeline.config import MYSQL_URL, POSTGRES_URL; print('MySQL:', MYSQL_URL[:30]); print('PG:', POSTGRES_URL[:30])"
```

Expected: both URLs print (passwords visible — that's fine locally).

- [ ] **Step 4: Commit**

```bash
git add pipeline/__init__.py pipeline/config.py
git commit -m "feat: add pipeline config module"
```

---

## Task 4: Database schema DDL

**Files:**
- Create: `sql/create_schemas.sql`

- [ ] **Step 1: Create `sql/` directory and `sql/create_schemas.sql`**

```sql
-- raw schema: mirrors MySQL source tables
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

-- analytics schema: aggregated output
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

- [ ] **Step 2: Apply the schema to the running container**

```bash
docker exec -i basket_craft_pg psql -U pipeline -d basket_craft < sql/create_schemas.sql
```

Expected: no errors; `CREATE SCHEMA`, `CREATE TABLE` messages printed.

- [ ] **Step 3: Verify tables exist**

```bash
docker exec basket_craft_pg psql -U pipeline -d basket_craft -c "\dt raw.*"
docker exec basket_craft_pg psql -U pipeline -d basket_craft -c "\dt analytics.*"
```

Expected: `raw.orders`, `raw.order_items`, `raw.products`, `analytics.monthly_sales_summary` listed.

- [ ] **Step 4: Commit**

```bash
git add sql/create_schemas.sql
git commit -m "feat: add database schema DDL"
```

---

## Task 5: Transform SQL

**Files:**
- Create: `sql/monthly_summary.sql`

- [ ] **Step 1: Create `sql/monthly_summary.sql`**

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

- [ ] **Step 2: Commit**

```bash
git add sql/monthly_summary.sql
git commit -m "feat: add monthly_summary transform SQL"
```

---

## Task 6: Test fixtures

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import pytest
import pandas as pd
from sqlalchemy import create_engine, text
from pipeline.config import POSTGRES_URL


@pytest.fixture(scope="session")
def pg_engine():
    return create_engine(POSTGRES_URL)


@pytest.fixture
def raw_fixture(pg_engine):
    """Load minimal known data into raw.* tables for unit testing."""
    orders = pd.DataFrame([
        {"order_id": 1, "customer_id": 101, "order_date": "2024-01-15", "status": "complete"},
        {"order_id": 2, "customer_id": 102, "order_date": "2024-01-20", "status": "complete"},
        {"order_id": 3, "customer_id": 103, "order_date": "2024-02-10", "status": "complete"},
    ])
    order_items = pd.DataFrame([
        # Jan: order 1 → Classic Basket, 2 units @ $25 = $50
        {"order_item_id": 1, "order_id": 1, "product_id": 1, "quantity": 2, "price_usd": 25.00},
        # Jan: order 2 → Gift Basket, 1 unit @ $40 = $40
        {"order_item_id": 2, "order_id": 2, "product_id": 2, "quantity": 1, "price_usd": 40.00},
        # Feb: order 3 → Classic Basket, 3 units @ $25 = $75
        {"order_item_id": 3, "order_id": 3, "product_id": 1, "quantity": 3, "price_usd": 25.00},
    ])
    products = pd.DataFrame([
        {"product_id": 1, "product_name": "Classic Basket", "category_id": 1},
        {"product_id": 2, "product_name": "Gift Basket", "category_id": 2},
    ])

    orders.to_sql("orders", pg_engine, schema="raw", if_exists="replace", index=False)
    order_items.to_sql("order_items", pg_engine, schema="raw", if_exists="replace", index=False)
    products.to_sql("products", pg_engine, schema="raw", if_exists="replace", index=False)

    yield pg_engine

    with pg_engine.begin() as conn:
        conn.execute(text("TRUNCATE raw.orders, raw.order_items, raw.products"))
        conn.execute(text("TRUNCATE analytics.monthly_sales_summary"))
```

- [ ] **Step 2: Verify conftest loads without errors**

```bash
pytest tests/ --collect-only
```

Expected: 0 test items collected, no import errors.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "feat: add pytest fixtures for pipeline tests"
```

---

## Task 7: Transform module (TDD)

**Files:**
- Create: `pipeline/transform.py`
- Create: `tests/test_pipeline.py` (unit tests section)

- [ ] **Step 1: Write failing unit tests in `tests/test_pipeline.py`**

```python
from sqlalchemy import text


# ── Unit tests: transform SQL logic against fixture data ──────────────────────

def test_transform_produces_rows(raw_fixture):
    from pipeline.transform import transform
    transform()
    with raw_fixture.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM analytics.monthly_sales_summary")
        ).scalar()
    assert count > 0


def test_transform_expected_columns(raw_fixture):
    from pipeline.transform import transform
    transform()
    with raw_fixture.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM analytics.monthly_sales_summary LIMIT 1")
        ).mappings().first()
    assert set(row.keys()) == {
        "month", "product_name", "total_revenue",
        "order_count", "avg_order_value", "total_items_sold", "loaded_at",
    }


def test_transform_no_nulls(raw_fixture):
    from pipeline.transform import transform
    transform()
    with raw_fixture.connect() as conn:
        nulls = conn.execute(text("""
            SELECT COUNT(*) FROM analytics.monthly_sales_summary
            WHERE month IS NULL OR product_name IS NULL
               OR total_revenue IS NULL OR order_count IS NULL
               OR avg_order_value IS NULL OR total_items_sold IS NULL
        """)).scalar()
    assert nulls == 0


def test_revenue_jan_classic_basket(raw_fixture):
    """Jan: order 1 = 2 × $25 = $50 for Classic Basket."""
    from pipeline.transform import transform
    transform()
    with raw_fixture.connect() as conn:
        revenue = conn.execute(text("""
            SELECT total_revenue FROM analytics.monthly_sales_summary
            WHERE product_name = 'Classic Basket' AND month = '2024-01-01'
        """)).scalar()
    assert float(revenue) == 50.0


def test_order_count_jan_classic_basket(raw_fixture):
    """Jan Classic Basket: 1 distinct order."""
    from pipeline.transform import transform
    transform()
    with raw_fixture.connect() as conn:
        count = conn.execute(text("""
            SELECT order_count FROM analytics.monthly_sales_summary
            WHERE product_name = 'Classic Basket' AND month = '2024-01-01'
        """)).scalar()
    assert count == 1


def test_total_items_sold_feb(raw_fixture):
    """Feb Classic Basket: 3 items sold."""
    from pipeline.transform import transform
    transform()
    with raw_fixture.connect() as conn:
        items = conn.execute(text("""
            SELECT total_items_sold FROM analytics.monthly_sales_summary
            WHERE product_name = 'Classic Basket' AND month = '2024-02-01'
        """)).scalar()
    assert items == 3
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
pytest tests/test_pipeline.py -v
```

Expected: `ImportError: cannot import name 'transform' from 'pipeline.transform'` (module doesn't exist yet).

- [ ] **Step 3: Create `pipeline/transform.py`**

```python
from pathlib import Path
from sqlalchemy import create_engine, text
from pipeline.config import POSTGRES_URL


def transform():
    sql = Path("sql/monthly_summary.sql").read_text()
    # SQLAlchemy executes one statement at a time — split on semicolons
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    engine = create_engine(POSTGRES_URL)
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM analytics.monthly_sales_summary")
        ).scalar()

    if count == 0:
        raise RuntimeError("Transform produced 0 rows — check raw.* tables and SQL")

    print(f"  Transform complete: {count} rows in analytics.monthly_sales_summary")
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
pytest tests/test_pipeline.py -v
```

Expected: all 6 unit tests pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/transform.py tests/test_pipeline.py
git commit -m "feat: add transform module and unit tests"
```

---

## Task 8: Extract module (TDD)

**Files:**
- Modify: `tests/test_pipeline.py` (add extract tests)
- Create: `pipeline/extract.py`

- [ ] **Step 1: Add extract unit tests to `tests/test_pipeline.py`**

Append these to the existing file:

```python
# ── Unit tests: extract (requires MySQL connection) ───────────────────────────

def test_extract_loads_raw_tables(pg_engine):
    from pipeline.extract import extract
    extract()
    with pg_engine.connect() as conn:
        orders_count = conn.execute(text("SELECT COUNT(*) FROM raw.orders")).scalar()
        items_count = conn.execute(text("SELECT COUNT(*) FROM raw.order_items")).scalar()
        products_count = conn.execute(text("SELECT COUNT(*) FROM raw.products")).scalar()
    assert orders_count > 0
    assert items_count > 0
    assert products_count > 0


def test_extract_raw_orders_has_expected_columns(pg_engine):
    from pipeline.extract import extract
    extract()
    with pg_engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM raw.orders LIMIT 1")).mappings().first()
    assert {"order_id", "customer_id", "order_date", "status"}.issubset(set(row.keys()))


def test_extract_raw_order_items_has_price(pg_engine):
    from pipeline.extract import extract
    extract()
    with pg_engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM raw.order_items LIMIT 1")).mappings().first()
    assert "price_usd" in row.keys()
    assert row["price_usd"] is not None
```

- [ ] **Step 2: Run new tests — verify they FAIL**

```bash
pytest tests/test_pipeline.py::test_extract_loads_raw_tables -v
```

Expected: `ImportError: cannot import name 'extract' from 'pipeline.extract'`.

- [ ] **Step 3: Create `pipeline/extract.py`**

```python
import pandas as pd
from sqlalchemy import create_engine, inspect
from pipeline.config import MYSQL_URL, POSTGRES_URL

EXPECTED_COLUMNS = {
    "orders":      {"order_id", "customer_id", "order_date", "status"},
    "order_items": {"order_item_id", "order_id", "product_id", "quantity", "price_usd"},
    "products":    {"product_id", "product_name", "category_id"},
}


def extract():
    mysql_engine = create_engine(MYSQL_URL)
    pg_engine = create_engine(POSTGRES_URL)

    # Schema drift check
    inspector = inspect(mysql_engine)
    for table, expected_cols in EXPECTED_COLUMNS.items():
        actual_cols = {col["name"] for col in inspector.get_columns(table)}
        missing = expected_cols - actual_cols
        if missing:
            raise RuntimeError(
                f"Schema drift detected in MySQL table '{table}': "
                f"missing columns {missing}"
            )

    # Extract and load each table into raw.*
    with mysql_engine.connect() as conn:
        for table in EXPECTED_COLUMNS:
            df = pd.read_sql(f"SELECT * FROM {table}", conn)
            if df.empty:
                raise RuntimeError(f"MySQL table '{table}' returned 0 rows")
            df.to_sql(table, pg_engine, schema="raw", if_exists="replace", index=False)
            print(f"  Loaded {len(df):,} rows into raw.{table}")
```

- [ ] **Step 4: Run extract tests — verify they PASS**

```bash
pytest tests/test_pipeline.py::test_extract_loads_raw_tables tests/test_pipeline.py::test_extract_raw_orders_has_expected_columns tests/test_pipeline.py::test_extract_raw_order_items_has_price -v
```

Expected: all 3 pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/test_pipeline.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/extract.py tests/test_pipeline.py
git commit -m "feat: add extract module and extract tests"
```

---

## Task 9: Entry point

**Files:**
- Create: `run_pipeline.py`

- [ ] **Step 1: Create `run_pipeline.py`**

```python
import sys
from pipeline.extract import extract
from pipeline.transform import transform


def main():
    try:
        print("[1/2] Extracting MySQL → raw schema...")
        extract()
        print("[2/2] Transforming raw → analytics...")
        transform()
        print("[OK] Pipeline complete")
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the pipeline end-to-end**

```bash
python run_pipeline.py
```

Expected output:
```
[1/2] Extracting MySQL → raw schema...
  Loaded X rows into raw.orders
  Loaded X rows into raw.order_items
  Loaded X rows into raw.products
[2/2] Transforming raw → analytics...
  Transform complete: X rows in analytics.monthly_sales_summary
[OK] Pipeline complete
```

- [ ] **Step 3: Verify the analytics table in PostgreSQL**

```bash
docker exec basket_craft_pg psql -U pipeline -d basket_craft \
  -c "SELECT month, product_name, total_revenue, order_count FROM analytics.monthly_sales_summary ORDER BY month, product_name LIMIT 10;"
```

Expected: rows with dates, product names, and positive revenue figures.

- [ ] **Step 4: Commit**

```bash
git add run_pipeline.py
git commit -m "feat: add pipeline entry point"
```

---

## Task 10: Smoke test

**Files:**
- Modify: `tests/test_pipeline.py` (append smoke test)

- [ ] **Step 1: Append smoke test to `tests/test_pipeline.py`**

```python
# ── Smoke test: full end-to-end run against real MySQL ────────────────────────

def test_smoke_full_pipeline(pg_engine):
    """Runs extract + transform against the real MySQL DB and verifies output."""
    from pipeline.extract import extract
    from pipeline.transform import transform

    extract()
    transform()

    with pg_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM analytics.monthly_sales_summary")
        ).scalar()
        row = conn.execute(
            text("SELECT * FROM analytics.monthly_sales_summary LIMIT 1")
        ).mappings().first()

    assert count > 0, "Expected rows in analytics.monthly_sales_summary"
    assert row["total_revenue"] is not None
    assert float(row["total_revenue"]) > 0
    assert row["order_count"] > 0
    assert row["total_items_sold"] > 0
    assert row["loaded_at"] is not None
```

- [ ] **Step 2: Run the smoke test**

```bash
pytest tests/test_pipeline.py::test_smoke_full_pipeline -v
```

Expected: PASS — rows extracted from MySQL, loaded to raw, transformed to analytics.

- [ ] **Step 3: Run the full test suite one final time**

```bash
pytest tests/test_pipeline.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_pipeline.py
git commit -m "feat: add smoke test for full pipeline run"
```

---

## Task 11: Update pipeline diagram

**Files:**
- Modify: `pipeline_diagram.md`

- [ ] **Step 1: Replace `pipeline_diagram.md` with the final ELT design**

```markdown
# Basket Craft Data Pipeline

## Architecture Diagram

\`\`\`mermaid
flowchart LR
    subgraph SOURCE["☁ Source — MySQL (db.isba.co)"]
        direction TB
        T1[(orders)]
        T2[(order_items)]
        T3[(products)]
    end

    subgraph EXTRACT["① Extract"]
        E1[pipeline/extract.py\nSQLAlchemy + PyMySQL\npandas to_sql]
    end

    subgraph RAW["② Stage — raw schema"]
        direction TB
        R1[(raw.orders)]
        R2[(raw.order_items)]
        R3[(raw.products)]
    end

    subgraph TRANSFORM["③ Transform"]
        TF1[pipeline/transform.py\nSQL in PostgreSQL\nJoin + GROUP BY]
    end

    subgraph DEST["🐘 Destination — PostgreSQL (Docker)"]
        direction TB
        D1[(analytics.monthly_sales_summary)]
    end

    SOURCE --> EXTRACT --> RAW --> TRANSFORM --> DEST
\`\`\`

## Target Table Schema

**`analytics.monthly_sales_summary`** (PostgreSQL)

| Column             | Type      | Description                          |
|--------------------|-----------|--------------------------------------|
| `month`            | DATE      | First day of the month (YYYY-MM-01)  |
| `product_name`     | VARCHAR   | Product name (used as category)      |
| `total_revenue`    | DECIMAL   | SUM(quantity × price_usd)            |
| `order_count`      | INTEGER   | COUNT(DISTINCT order_id)             |
| `avg_order_value`  | DECIMAL   | total_revenue / order_count          |
| `total_items_sold` | INTEGER   | SUM(quantity)                        |
| `loaded_at`        | TIMESTAMP | When the pipeline last ran           |

## Source Tables (MySQL)

| Table          | Key Columns                                              |
|----------------|----------------------------------------------------------|
| `orders`       | order_id, customer_id, order_date, status                |
| `order_items`  | order_item_id, order_id, product_id, quantity, price_usd |
| `products`     | product_id, product_name, category_id                    |
```

- [ ] **Step 2: Commit**

```bash
git add pipeline_diagram.md
git commit -m "docs: update pipeline diagram to reflect ELT design"
```
