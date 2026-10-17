-- Échoue si une banque a plusieurs valeurs pour le même KPI.
select lei_code, kpi, count(*) as n
from {{ ref('fct_bank_kpis') }}
group by 1, 2
having count(*) > 1
