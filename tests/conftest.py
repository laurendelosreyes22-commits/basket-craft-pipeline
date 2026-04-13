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
