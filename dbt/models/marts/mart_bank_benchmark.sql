-- Vue large pour Power BI : une ligne par banque, une colonne par KPI.
-- Colonnes *_eba : source officielle EBA. Autres colonnes : rapports annuels (extraction Claude).
select
    lei_code,
    bank_name,
    country,
    period_end,
    max(case when kpi = 'cet1_ratio'             then value_eba end)    as cet1_ratio_eba,
    max(case when kpi = 'total_capital_ratio'    then value_eba end)    as total_capital_ratio_eba,
    max(case when kpi = 'leverage_ratio'         then value_eba end)    as leverage_ratio_eba,
    max(case when kpi = 'cet1_ratio'             then value_report end) as cet1_ratio,
    max(case when kpi = 'total_capital_ratio'    then value_report end) as total_capital_ratio,
    max(case when kpi = 'leverage_ratio'         then value_report end) as leverage_ratio,
    max(case when kpi = 'net_banking_income'     then value_report end) as net_banking_income_meur,
    max(case when kpi = 'cost_income_ratio'      then value_report end) as cost_income_ratio,
    max(case when kpi = 'cost_of_risk_bp'        then value_report end) as cost_of_risk_bp,
    max(case when kpi = 'net_income_group_share' then value_report end) as net_income_group_share_meur,
    max(case when kpi = 'rote'                   then value_report end) as rote
from {{ ref('fct_bank_kpis') }}
group by all
