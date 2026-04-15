{{ config(materialized='table') }}

select
    product_id,
    product_name,
    product_description,
    created_at::date    as product_launch_date
from {{ ref('stg_products') }}
