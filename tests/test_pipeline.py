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
