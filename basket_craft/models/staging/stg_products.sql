select
    product_id,
    created_at::timestamp   as created_at,
    product_name,
    description             as product_description
from {{ source('raw', 'products') }}
