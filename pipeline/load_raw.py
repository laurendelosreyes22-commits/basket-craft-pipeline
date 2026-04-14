import pandas as pd
from sqlalchemy import create_engine, inspect, text
from pipeline.config import MYSQL_URL, RDS_URL


def load_raw():
    mysql_engine = create_engine(MYSQL_URL)
    rds_engine = create_engine(RDS_URL)

    # Ensure raw schema exists in RDS
    with rds_engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))

    inspector = inspect(mysql_engine)
    tables = inspector.get_table_names()

    if not tables:
        raise RuntimeError("No tables found in MySQL database")

    print(f"Found {len(tables)} tables in MySQL: {', '.join(tables)}")

    with mysql_engine.connect() as conn:
        for table in tables:
            df = pd.read_sql(f"SELECT * FROM `{table}`", conn)
            df.to_sql(table, rds_engine, schema="raw", if_exists="replace", index=False)
            print(f"  Loaded {len(df):,} rows into raw.{table}")

    print("Done.")
