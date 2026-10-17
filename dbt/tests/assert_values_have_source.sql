-- Traçabilité : toute valeur extraite doit avoir une page et une citation.
select *
from {{ ref('fct_bank_kpis') }}
where value_report is not null
  and (source_page is null or quote is null or quote = '')
