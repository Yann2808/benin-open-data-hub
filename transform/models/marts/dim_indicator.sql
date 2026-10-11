with en_names as (
    select indicator_code, any_value(indicator_name_en) as indicator_name_en
    from {{ ref('stg_wb_observations') }}
    group by 1
)

select
    c.indicator_code,
    c.label_fr,
    e.indicator_name_en,
    c.theme,
    c.unit_fr,
    c.higher_is_better,
    'World Bank — World Development Indicators'                        as source_name,
    'https://data.worldbank.org/indicator/' || c.indicator_code         as source_url
from {{ ref('stg_indicator_catalog') }} c
left join en_names e using (indicator_code)
