-- Garde-fou métier : un ratio CET1 hors de [5 % ; 40 %] ou un ratio de levier
-- hors de [2 % ; 15 %] est presque toujours une erreur d'extraction ou d'unité.
select *
from {{ ref('fct_bank_kpis') }}
where (kpi = 'cet1_ratio' and value_report not between 5 and 40)
   or (kpi = 'total_capital_ratio' and value_report not between 8 and 50)
   or (kpi = 'leverage_ratio' and value_report not between 2 and 15)
   or (kpi = 'cost_income_ratio' and value_report not between 20 and 120)
