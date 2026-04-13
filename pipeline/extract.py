import pandas as pd
from sqlalchemy import create_engine, inspect
from pipeline.config import MYSQL_URL, POSTGRES_URL

EXPECTED_COLUMNS = {
    "orders":      {"order_id", "customer_id", "order_date", "status"},
    "order_items": {"order_item_id", "order_id", "product_id", "quantity", "price_usd"},
    "products":    {"product_id", "product_name", "category_id"},
}

# Map MySQL column names -> expected column names when they differ
COLUMN_RENAMES = {
    "orders": {
        "user_id":    "customer_id",
        "created_at": "order_date",
    },
    "order_items": {},
    "products": {},
}

# Columns to add with a constant/default value when missing from MySQL
COLUMN_DEFAULTS = {
    "orders": {
        "status": "completed",
    },
    "order_items": {
        "quantity": 1,
    },
    "products": {
        "category_id": None,
    },
}


def extract():
    mysql_engine = create_engine(MYSQL_URL)
    pg_engine = create_engine(POSTGRES_URL)

    inspector = inspect(mysql_engine)

    with mysql_engine.connect() as conn:
        for table in EXPECTED_COLUMNS:
            df = pd.read_sql(f"SELECT * FROM {table}", conn)

            if df.empty:
                raise RuntimeError(f"MySQL table '{table}' returned 0 rows")

            # Rename columns to match expected schema
            renames = COLUMN_RENAMES.get(table, {})
            if renames:
                df = df.rename(columns=renames)

            # Add missing columns with defaults
            defaults = COLUMN_DEFAULTS.get(table, {})
            for col, default_val in defaults.items():
                if col not in df.columns:
                    df[col] = default_val

            # Schema drift check: verify all expected columns are now present
            expected = EXPECTED_COLUMNS[table]
            actual = set(df.columns)
            missing = expected - actual
            if missing:
                raise RuntimeError(
                    f"Schema drift detected for table '{table}': "
                    f"missing columns {missing} after rename/default mapping"
                )

            # Keep only the expected columns (plus any extras are fine to keep)
            df.to_sql(table, pg_engine, schema="raw", if_exists="replace", index=False)
            print(f"  Loaded {len(df):,} rows into raw.{table}")
