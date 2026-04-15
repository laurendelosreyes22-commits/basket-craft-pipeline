select
    order_item_id,
    created_at::timestamp       as created_at,
    order_id,
    product_id,
    is_primary_item::boolean    as is_primary_item,
    price_usd,
    cogs_usd
from {{ source('raw', 'order_items') }}
