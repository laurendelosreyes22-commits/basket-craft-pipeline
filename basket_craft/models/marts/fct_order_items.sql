{{ config(materialized='table') }}

select
    -- keys
    oi.order_item_id,
    oi.order_id,
    o.customer_id,
    oi.product_id,
    o.created_at::date      as order_date,

    -- attributes
    oi.is_primary_item,

    -- measures
    1                       as quantity,
    oi.price_usd            as unit_price_usd,
    1 * oi.price_usd        as line_total_usd,
    oi.cogs_usd             as line_cogs_usd
from {{ ref('stg_order_items') }} oi
left join {{ ref('stg_orders') }} o on oi.order_id = o.order_id
