# Snowflake Loader Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `pipeline/load_snowflake.py` to add context manager connection safety, uppercase identifier casing, post-load row count validation, structured logging, and a direct-run entrypoint.

**Architecture:** All changes are confined to a single file (`pipeline/load_snowflake.py`). A new test file (`tests/test_load_snowflake.py`) covers the two testable behaviors — identifier casing and row count validation — using `unittest.mock` so no live credentials are needed. Structural changes (context managers, logging, entrypoint) are verified by running the full test suite after each step.

**Tech Stack:** Python 3, `snowflake-connector-python`, `snowflake.connector.pandas_tools.write_pandas`, `sqlalchemy`, `pandas`, `pytest`, `unittest.mock`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `tests/test_load_snowflake.py` | Unit tests — identifier casing and row count validation |
| Modify | `pipeline/load_snowflake.py` | All refactor changes |

---

## Task 1: Write failing tests for identifier casing

**Files:**
- Create: `tests/test_load_snowflake.py`

- [ ] **Step 1: Create the test file with env fixture and casing tests**

```python
# tests/test_load_snowflake.py
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from pipeline.load_snowflake import load_snowflake


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("RDS_USER", "user")
    monkeypatch.setenv("RDS_PASSWORD", "pass")
    monkeypatch.setenv("RDS_HOST", "localhost")
    monkeypatch.setenv("RDS_PORT", "5432")
    monkeypatch.setenv("RDS_DATABASE", "db")
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "acct")
    monkeypatch.setenv("SNOWFLAKE_USER", "sfuser")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "sfpass")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "wh")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "BASKET_CRAFT")
    monkeypatch.setenv("SNOWFLAKE_SCHEMA", "RAW")


def _make_mocks(tables, row_counts):
    """Return (sf_conn, engine, inspector_mock, cursor_mock) wired together."""
    # Snowflake cursor — returns COUNT(*) values in order
    cursor = MagicMock()
    cursor.fetchone.side_effect = [(n,) for n in row_counts]

    # Snowflake connection — context manager
    sf_conn = MagicMock()
    sf_conn.__enter__ = MagicMock(return_value=sf_conn)
    sf_conn.__exit__ = MagicMock(return_value=False)
    sf_conn.cursor.return_value = cursor

    # RDS connection — context manager
    rds_conn = MagicMock()
    rds_conn.__enter__ = MagicMock(return_value=rds_conn)
    rds_conn.__exit__ = MagicMock(return_value=False)

    # SQLAlchemy engine
    engine = MagicMock()
    engine.connect.return_value = rds_conn

    # Inspector
    inspector = MagicMock()
    inspector.get_table_names.return_value = tables

    return sf_conn, engine, inspector, cursor


def test_columns_are_uppercased(mock_env):
    """DataFrame column names must be uppercase before write_pandas is called."""
    tables = ["orders"]
    df = pd.DataFrame([{"order_id": 1, "customer_id": 101}])
    sf_conn, engine, inspector, _ = _make_mocks(tables, row_counts=[1])

    with (
        patch("pipeline.load_snowflake.create_engine", return_value=engine),
        patch("pipeline.load_snowflake.inspect", return_value=inspector),
        patch("pipeline.load_snowflake.snowflake.connector.connect", return_value=sf_conn),
        patch("pipeline.load_snowflake.pd.read_sql", return_value=df),
        patch("pipeline.load_snowflake.write_pandas") as mock_wp,
    ):
        mock_wp.return_value = (True, 1, 1, "")
        load_snowflake()

    called_df = mock_wp.call_args[0][1]
    assert list(called_df.columns) == ["ORDER_ID", "CUSTOMER_ID"]


def test_table_name_is_uppercase(mock_env):
    """table_name passed to write_pandas must be uppercase."""
    tables = ["orders"]
    df = pd.DataFrame([{"order_id": 1}])
    sf_conn, engine, inspector, _ = _make_mocks(tables, row_counts=[1])

    with (
        patch("pipeline.load_snowflake.create_engine", return_value=engine),
        patch("pipeline.load_snowflake.inspect", return_value=inspector),
        patch("pipeline.load_snowflake.snowflake.connector.connect", return_value=sf_conn),
        patch("pipeline.load_snowflake.pd.read_sql", return_value=df),
        patch("pipeline.load_snowflake.write_pandas") as mock_wp,
    ):
        mock_wp.return_value = (True, 1, 1, "")
        load_snowflake()

    assert mock_wp.call_args[1]["table_name"] == "ORDERS"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /path/to/basket-craft-pipeline
.venv/bin/pytest tests/test_load_snowflake.py -v
```

Expected: Both tests FAIL. The current code lowercases columns and passes the table name as-is.

---

## Task 2: Implement uppercase identifier casing

**Files:**
- Modify: `pipeline/load_snowflake.py`

- [ ] **Step 1: Change column lowercasing to uppercasing and uppercase the table_name arg**

In `pipeline/load_snowflake.py`, locate the loop body and replace:

```python
df.columns = [c.lower() for c in df.columns]

write_pandas(
    sf_conn,
    df,
    table_name=table,
    database=database,
    schema=schema,
    quote_identifiers=False,
    auto_create_table=True,
    overwrite=True,
)
```

With:

```python
df.columns = [c.upper() for c in df.columns]

write_pandas(
    sf_conn,
    df,
    table_name=table.upper(),
    database=database,
    schema=schema,
    quote_identifiers=False,
    auto_create_table=True,
    overwrite=True,
)
```

- [ ] **Step 2: Run the casing tests to confirm they pass**

```bash
.venv/bin/pytest tests/test_load_snowflake.py::test_columns_are_uppercased tests/test_load_snowflake.py::test_table_name_is_uppercase -v
```

Expected: Both tests PASS.

- [ ] **Step 3: Commit**

```bash
git add pipeline/load_snowflake.py tests/test_load_snowflake.py
git commit -m "feat: uppercase column names and table name for Snowflake identifier casing"
```

---

## Task 3: Write failing tests for row count validation

**Files:**
- Modify: `tests/test_load_snowflake.py`

- [ ] **Step 1: Add two validation tests to the test file**

Append to `tests/test_load_snowflake.py`:

```python
def test_row_count_mismatch_raises(mock_env):
    """RuntimeError must be raised when Snowflake COUNT(*) does not match len(df)."""
    tables = ["orders"]
    df = pd.DataFrame([{"order_id": 1}, {"order_id": 2}])  # 2 rows
    sf_conn, engine, inspector, _ = _make_mocks(tables, row_counts=[1])  # Snowflake returns 1

    with (
        patch("pipeline.load_snowflake.create_engine", return_value=engine),
        patch("pipeline.load_snowflake.inspect", return_value=inspector),
        patch("pipeline.load_snowflake.snowflake.connector.connect", return_value=sf_conn),
        patch("pipeline.load_snowflake.pd.read_sql", return_value=df),
        patch("pipeline.load_snowflake.write_pandas") as mock_wp,
    ):
        mock_wp.return_value = (True, 1, 2, "")
        with pytest.raises(RuntimeError, match="orders"):
            load_snowflake()


def test_row_count_match_does_not_raise(mock_env):
    """No error when Snowflake COUNT(*) matches the number of rows sent."""
    tables = ["orders"]
    df = pd.DataFrame([{"order_id": 1}, {"order_id": 2}])  # 2 rows
    sf_conn, engine, inspector, _ = _make_mocks(tables, row_counts=[2])  # Snowflake returns 2

    with (
        patch("pipeline.load_snowflake.create_engine", return_value=engine),
        patch("pipeline.load_snowflake.inspect", return_value=inspector),
        patch("pipeline.load_snowflake.snowflake.connector.connect", return_value=sf_conn),
        patch("pipeline.load_snowflake.pd.read_sql", return_value=df),
        patch("pipeline.load_snowflake.write_pandas") as mock_wp,
    ):
        mock_wp.return_value = (True, 1, 2, "")
        load_snowflake()  # must not raise
```

- [ ] **Step 2: Run to confirm the new tests fail**

```bash
.venv/bin/pytest tests/test_load_snowflake.py::test_row_count_mismatch_raises tests/test_load_snowflake.py::test_row_count_match_does_not_raise -v
```

Expected: Both FAIL. The current code has no COUNT(*) validation.

---

## Task 4: Implement row count validation

**Files:**
- Modify: `pipeline/load_snowflake.py`

- [ ] **Step 1: Add COUNT(*) check after write_pandas in the loop body**

After the `write_pandas(...)` call, add:

```python
cursor = sf_conn.cursor()
cursor.execute(f"SELECT COUNT(*) FROM {database}.{schema}.{table}")
sf_count = cursor.fetchone()[0]
cursor.close()

if sf_count != len(df):
    raise RuntimeError(
        f"{table}: sent {len(df):,} rows but Snowflake has {sf_count:,}"
    )
```

- [ ] **Step 2: Run all four tests to confirm they pass**

```bash
.venv/bin/pytest tests/test_load_snowflake.py -v
```

Expected: All four tests PASS.

- [ ] **Step 3: Commit**

```bash
git add pipeline/load_snowflake.py tests/test_load_snowflake.py
git commit -m "feat: add post-load row count validation against Snowflake"
```

---

## Task 5: Refactor connections, logging, and entrypoint

**Files:**
- Modify: `pipeline/load_snowflake.py`

- [ ] **Step 1: Replace the full contents of `pipeline/load_snowflake.py` with the refactored version**

```python
import logging
import os

import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def load_snowflake():
    rds_engine = create_engine(
        "postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}".format(
            user=os.environ["RDS_USER"],
            password=os.environ["RDS_PASSWORD"],
            host=os.environ["RDS_HOST"],
            port=os.environ["RDS_PORT"],
            db=os.environ["RDS_DATABASE"],
        )
    )

    database = os.environ["SNOWFLAKE_DATABASE"]
    schema = os.environ["SNOWFLAKE_SCHEMA"]

    inspector = inspect(rds_engine)
    tables = inspector.get_table_names(schema="raw")

    if not tables:
        raise RuntimeError("No tables found in RDS raw schema")

    logger.info("Found %d tables in RDS raw schema: %s", len(tables), ", ".join(tables))

    with snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=database,
        schema=schema,
        **({} if not os.environ.get("SNOWFLAKE_ROLE") else {"role": os.environ["SNOWFLAKE_ROLE"]}),
    ) as sf_conn:
        with rds_engine.connect() as rds_conn:
            for table in tables:
                df = pd.read_sql(text(f"SELECT * FROM raw.{table}"), rds_conn)
                df.columns = [c.upper() for c in df.columns]

                write_pandas(
                    sf_conn,
                    df,
                    table_name=table.upper(),
                    database=database,
                    schema=schema,
                    quote_identifiers=False,
                    auto_create_table=True,
                    overwrite=True,
                )

                cursor = sf_conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {database}.{schema}.{table}")
                sf_count = cursor.fetchone()[0]
                cursor.close()

                if sf_count != len(df):
                    raise RuntimeError(
                        f"{table}: sent {len(df):,} rows but Snowflake has {sf_count:,}"
                    )

                logger.info("  %s: %s rows verified in Snowflake", table, f"{sf_count:,}")

    logger.info("Done. Loaded %d tables.", len(tables))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    try:
        load_snowflake()
    except Exception as exc:
        logging.error("Pipeline failed: %s", exc)
        raise SystemExit(1)
```

- [ ] **Step 2: Run the full test suite to confirm nothing regressed**

```bash
.venv/bin/pytest tests/test_load_snowflake.py -v
```

Expected: All four tests PASS.

- [ ] **Step 3: Commit**

```bash
git add pipeline/load_snowflake.py
git commit -m "refactor: add context managers, structured logging, and __main__ entrypoint to Snowflake loader"
```

---

## Task 6: Verify direct invocation works

**Files:** None

- [ ] **Step 1: Confirm the module is importable and the entrypoint is wired**

```bash
.venv/bin/python -c "import pipeline.load_snowflake; print('import OK')"
```

Expected output: `import OK`

- [ ] **Step 2: Confirm the -m invocation prints help on missing env (not a traceback from bad imports)**

```bash
.venv/bin/python -m pipeline.load_snowflake 2>&1 | head -5
```

Expected: A log line or `KeyError` for a missing env var — not an `ImportError` or `SyntaxError`.

- [ ] **Step 3: Run the full project test suite one final time**

```bash
.venv/bin/pytest tests/ -v
```

Expected: All tests PASS (existing `test_pipeline.py` tests require `docker compose up -d` and initialized schemas first — skip if Docker is not running).
