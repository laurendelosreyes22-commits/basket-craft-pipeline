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
