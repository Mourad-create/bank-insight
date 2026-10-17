-- Une ligne par banque × date de référence × item EBA, montant typé.
with source as (
    select * from {{ source('raw', 'eba_transparency') }}
)

select
    trim(lei_code)                                              as lei_code,
    trim(item)                                                  as eba_item,
    label                                                       as eba_label,
    -- La période EBA est au format AAAAMM : on la convertit en dernier jour du mois.
    last_day(strptime(trim(period) || '01', '%Y%m%d'))::date    as period_end,
    try_cast(replace(amount, ',', '.') as double)               as amount,
    source_file
from source
where try_cast(replace(amount, ',', '.') as double) is not null
