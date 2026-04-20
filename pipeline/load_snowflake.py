import os
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv

load_dotenv()


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

    sf_conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
        **({} if not os.environ.get("SNOWFLAKE_ROLE") else {"role": os.environ["SNOWFLAKE_ROLE"]}),
    )

    inspector = inspect(rds_engine)
    tables = inspector.get_table_names(schema="raw")

    if not tables:
        raise RuntimeError("No tables found in RDS raw schema")

    print(f"Found {len(tables)} tables in RDS raw schema: {', '.join(tables)}")

    database = os.environ["SNOWFLAKE_DATABASE"]
    schema = os.environ["SNOWFLAKE_SCHEMA"]

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

            print(f"  Loaded {len(df):,} rows into {database}.{schema}.{table}")

    sf_conn.close()
    print("Done.")
