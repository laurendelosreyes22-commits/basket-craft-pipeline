# Basket Craft Data Pipeline

## Architecture Diagram

```mermaid
flowchart LR
    subgraph SOURCE["☁ Source — MySQL (Basket Craft)"]
        direction TB
        T1[(orders)]
        T2[(order_items)]
        T3[(products)]
        T4[(categories)]
    end

    subgraph EXTRACT["① Extract"]
        E1[Python\nSQLAlchemy\n+ PyMySQL]
    end

    subgraph TRANSFORM["② Transform"]
        direction TB
        TF1[Join:\norders → order_items\n→ products → categories]
        TF2[Aggregate by\nmonth + category]
        TF3[Compute:\nRevenue\nOrder Count\nAvg Order Value]
        TF1 --> TF2 --> TF3
    end

    subgraph LOAD["③ Load"]
        L1[Python\nSQLAlchemy\n+ psycopg2]
    end

    subgraph DEST["🐘 Destination — PostgreSQL (Docker)"]
        direction TB
        D1[(monthly_sales_summary)]
    end

    SOURCE --> EXTRACT --> TRANSFORM --> LOAD --> DEST
```

## Target Table Schema

**`monthly_sales_summary`** (PostgreSQL)

| Column            | Type    | Description                          |
|-------------------|---------|--------------------------------------|
| `month`           | DATE    | First day of the month (YYYY-MM-01)  |
| `category_name`   | TEXT    | Product category                     |
| `revenue`         | NUMERIC | SUM(quantity × unit_price)           |
| `order_count`     | INTEGER | COUNT(DISTINCT order_id)             |
| `avg_order_value` | NUMERIC | revenue / order_count                |

## Source Tables (MySQL)

| Table          | Key Columns                                         |
|----------------|-----------------------------------------------------|
| `orders`       | order_id, customer_id, order_date, status           |
| `order_items`  | order_item_id, order_id, product_id, quantity, unit_price |
| `products`     | product_id, product_name, category_id              |
| `categories`   | category_id, category_name                         |
```
