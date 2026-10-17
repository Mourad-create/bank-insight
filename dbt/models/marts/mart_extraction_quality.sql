-- Fiabilité de l'extraction : comparaison des valeurs lues par Claude
-- avec les valeurs officielles EBA, KPI par KPI.
-- Tolérance : 0,15 point de % (arrondis, phasé vs fully loaded à analyser à part).
{% set tolerance = var('match_tolerance_pts', 0.15) %}

select
    lei_code,
    bank_name,
    kpi,
    value_report,
    value_eba,
    round(value_report - value_eba, 3)             as gap_pts,
    case
        when value_report is null then 'non_trouve'
        when value_eba is null then 'pas_de_reference'
        when abs(value_report - value_eba) <= {{ tolerance }} then 'concordant'
        else 'ecart'
    end                                            as status,
    source_page,
    quote
from {{ ref('fct_bank_kpis') }}
where kpi in (select kpi from {{ ref('kpi_definitions') }} where comparable_eba)
