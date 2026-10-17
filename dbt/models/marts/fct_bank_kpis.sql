-- Table centrale : une ligne par banque × KPI à la date de référence.
--   value_report = valeur lue par Claude dans le rapport annuel (null tant que non extraite)
--   value_eba    = valeur officielle EBA (uniquement pour les ratios réglementaires)
{% set reference_date = var('reference_date', '2024-12-31') %}

with banks_x_kpis as (
    select b.lei_code, b.bank_name, b.country, k.kpi, k.label as kpi_label, k.unit as kpi_unit
    from {{ ref('stg_banks') }} b
    cross join {{ ref('kpi_definitions') }} k
),

eba as (
    select
        e.lei_code,
        m.kpi,
        e.amount * m.scale_to_percent as value_eba
    from {{ ref('stg_eba__transparency') }} e
    join {{ ref('eba_item_mapping') }} m
      on e.eba_item = m.eba_item
    where e.period_end = date '{{ reference_date }}'
),

reports as (
    select *
    from {{ ref('stg_reports__extracted_kpis') }}
)

select
    bk.lei_code,
    bk.bank_name,
    bk.country,
    bk.kpi,
    bk.kpi_label,
    bk.kpi_unit,
    date '{{ reference_date }}'  as period_end,
    r.value                      as value_report,
    round(eba.value_eba, 2)      as value_eba,
    r.source_file,
    r.source_page,
    r.quote,
    r.confidence,
    r.issues
from banks_x_kpis bk
left join reports r on r.lei_code = bk.lei_code and r.kpi = bk.kpi
left join eba on eba.lei_code = bk.lei_code and eba.kpi = bk.kpi
