select
    lei_code,
    bank_name,
    country,
    report_pdf
from {{ source('raw', 'banks') }}
