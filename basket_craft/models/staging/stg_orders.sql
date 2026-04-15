select
    order_id,
    created_at::timestamp   as created_at,
    website_session_id,
    user_id                 as customer_id,
    primary_product_id,
    items_purchased,
    price_usd               as order_total_usd,
    cogs_usd                as order_cogs_usd
from {{ source('raw', 'orders') }}
