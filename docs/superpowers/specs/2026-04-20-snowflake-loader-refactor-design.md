# Snowflake Loader Refactor Design

**Date:** 2026-04-20  
**File:** `pipeline/load_snowflake.py`  
**Status:** Approved

---

## Summary

Refactor the existing `load_snowflake.py` to fix three structural gaps:

1. Snowflake connection is not closed on error (no context manager)
2. No post-load row count validation — silent type-coercion failures go undetected
3. Script cannot be run directly — requires awkward `python -c "from pipeline..."` invocation

The bulk-load mechanism (`write_pandas` via Snowflake's `COPY INTO`) is unchanged.

---

## Module Structure

Single file, no new files introduced.

```
pipeline/load_snowflake.py
├── module-level logger:  logger = logging.getLogger(__name__)
├── load_snowflake()      public function (called by automation or tests)
│     ├── create RDS SQLAlchemy engine
│     ├── open Snowflake connection (context manager)
│     ├── open RDS connection (context manager, nested inside Snowflake)
│     ├── discover tables via SQLAlchemy inspect()
│     └── for each table: read → lowercase columns → write_pandas → validate
└── if __name__ == "__main__":
      configure logging.basicConfig(level=INFO)
      call load_snowflake()
      catch exception → log error → raise SystemExit(1)
```

Runnable two ways:

```bash
# preferred — direct module invocation
.venv/bin/python -m pipeline.load_snowflake

# existing -c invocation still works unchanged
.venv/bin/python -c "from pipeline.load_snowflake import load_snowflake; load_snowflake()"
```

---

## Connection Management

Both connections are opened as context managers so cleanup is guaranteed even if an exception fires mid-loop.

```python
with snowflake.connector.connect(...) as sf_conn:
    with rds_engine.connect() as rds_conn:
        for table in tables:
            ...
```

**Nesting order:** Snowflake is the outer context because opening a Snowflake session has meaningful latency (warehouse resume + auth handshake). It is opened once and reused for all 8 tables. The RDS connection is the inner context.

The current `sf_conn.close()` call at the end of the function is removed — the `with` block handles it unconditionally.

---

## Row Count Validation

After each `write_pandas()` call, a `COUNT(*)` query runs against Snowflake to confirm rows landed. A mismatch raises immediately.

```python
write_pandas(sf_conn, df, table_name=table, ...)

cursor = sf_conn.cursor()
cursor.execute(f"SELECT COUNT(*) FROM {database}.{schema}.{table}")
sf_count = cursor.fetchone()[0]
cursor.close()

if sf_count != len(df):
    raise RuntimeError(
        f"{table}: sent {len(df):,} rows but Snowflake has {sf_count:,}"
    )
```

The query uses fully qualified `{database}.{schema}.{table}` identifiers sourced from `os.environ` and SQLAlchemy's table inspector — no user-supplied input reaches the string. The cursor is opened and closed manually (not via `with`) because Snowflake's cursor context manager support varies across connector versions.

**Why validate:** `write_pandas()` returns `success=True` when the `COPY INTO` command is accepted, not when all rows pass Snowflake's type validation. Rows that fail type coercion are silently skipped by default. The `COUNT(*)` check catches this.

---

## Logging

Replace all `print()` calls with `logger.info()`. Logger is bound to the module path (`pipeline.load_snowflake`) via `logging.getLogger(__name__)`.

Log points:

```python
logger.info("Found %d tables in RDS raw schema: %s", len(tables), ", ".join(tables))
logger.info("  %s: %s rows verified in Snowflake", table, f"{sf_count:,}")
logger.info("Done. Loaded %d tables.", len(tables))
```

Values are passed as `%s` arguments (not f-strings) so interpolation is skipped when the log level is disabled.

The `__main__` block configures logging and handles top-level exceptions:

```python
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

The `load_snowflake()` function itself never calls `basicConfig` — logging configuration is the caller's responsibility.

---

## What Does Not Change

- `write_pandas()` with `auto_create_table=True`, `overwrite=True`, `quote_identifiers=False` — bulk-load mechanism is unchanged
- Table auto-discovery via `SQLAlchemy inspect()` — no hardcoded table list
- Full-refresh strategy — every run truncates and reloads
- All credential sources (`RDS_*`, `SNOWFLAKE_*` env vars from `.env`)
- The function signature `load_snowflake()` — existing call sites are unaffected

---

## Out of Scope

- CLI flags (e.g., `--tables`) for selective table loading
- Retry logic on transient Snowflake errors
- Parallelizing table loads
