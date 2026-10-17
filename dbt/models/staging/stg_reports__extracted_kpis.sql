-- KPI extraits des rapports annuels par Claude.
with source as (
    select * from {{ source('raw', 'extracted_kpis') }}
)

select
    lei_code,
    bank_name,
    kpi,
    try_cast(value as double)          as value,
    unit,
    try_cast(period_end as date)       as period_end,
    source_file,
    try_cast(source_page as integer)   as source_page,
    quote,
    confidence,
    issues,
    model,
    try_cast(extracted_at as timestamp) as extracted_at
from source
