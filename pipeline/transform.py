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
