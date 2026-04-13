# Basket Craft Data Pipeline

## Architecture Diagram

```mermaid
flowchart LR
    subgraph SOURCE["☁ Source — MySQL (db.isba.co)"]
        direction TB
        T1[(orders)]
        T2[(order_items)]
        T3[(products)]
    end

    subgraph EXTRACT["① Extract"]
        E1[pipeline/extract.py\nSQLAlchemy + PyMySQL\npandas to_sql]
    end

    subgraph RAW["② Stage — raw schema"]
        direction TB
        R1[(raw.orders)]
        R2[(raw.order_items)]
        R3[(raw.products)]
    end

    subgraph TRANSFORM["③ Transform"]
        TF1[pipeline/transform.py\nSQL in PostgreSQL\nJoin + GROUP BY]
    end

    subgraph DEST["🐘 Destination — PostgreSQL (Docker)"]
        direction TB
        D1[(analytics.monthly_sales_summary)]
    end

    SOURCE --> EXTRACT --> RAW --> TRANSFORM --> DEST
```

## Target Table Schema

**`analytics.monthly_sales_summary`** (PostgreSQL)

| Column             | Type      | Description                          |
|--------------------|-----------|--------------------------------------|
| `month`            | DATE      | First day of the month (YYYY-MM-01)  |
| `product_name`     | VARCHAR   | Product name                         |
| `total_revenue`    | DECIMAL   | SUM(quantity × price_usd)            |
| `order_count`      | INTEGER   | COUNT(DISTINCT order_id)             |
| `avg_order_value`  | DECIMAL   | total_revenue / order_count          |
| `total_items_sold` | INTEGER   | SUM(quantity)                        |
| `loaded_at`        | TIMESTAMP | When the pipeline last ran           |

## Source Tables (MySQL)

| Table          | Key Columns                                              |
|----------------|----------------------------------------------------------|
| `orders`       | order_id, customer_id, order_date, status                |
| `order_items`  | order_item_id, order_id, product_id, quantity, price_usd |
| `products`     | product_id, product_name, category_id                    |
