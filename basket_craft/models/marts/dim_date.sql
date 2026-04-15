{{ config(materialized='table') }}

with date_spine as (
    select
        dateadd(day, seq4(), '2020-01-01'::date) as date_day
    from table(generator(rowcount => 3653))  -- ~10 years
)

select
    date_day,
    extract(year from date_day) as year,
    extract(quarter from date_day) as quarter,
    extract(month from date_day) as month_num,
    to_char(date_day, 'Mon') as month_name,
    extract(day from date_day) as day_of_month,
    extract(dow from date_day) as day_of_week_num,
    to_char(date_day, 'Dy') as day_of_week_name,
    case when extract(dow from date_day) in (0, 6) then true else false end as is_weekend
from date_spine
