TRUNCATE analytics.monthly_sales_summary;

INSERT INTO analytics.monthly_sales_summary
    (month, product_name, total_revenue, order_count, avg_order_value, total_items_sold, loaded_at)
SELECT
    DATE_TRUNC('month', o.order_date::DATE)::DATE    AS month,
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
    DATE_TRUNC('month', o.order_date::DATE)::DATE,
    p.product_name
ORDER BY
    month,
    product_name;
