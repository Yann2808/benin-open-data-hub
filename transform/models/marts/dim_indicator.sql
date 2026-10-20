with en_names as (
    select
        indicator_code,
        any_value(indicator_name_en) as indicator_name_en,
        -- Date de publication par la source (« lastupdated » de l'API), hors démo
        max(try_cast(source_last_updated as date)) filter (where not is_demo) as source_published_on
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
    c.section,
    m.name_source,
    m.definition,
    m.source_organization,
    e.source_published_on,
    'World Bank — World Development Indicators'                        as source_name,
    'https://data.worldbank.org/indicator/' || c.indicator_code         as source_url
from {{ ref('stg_indicator_catalog') }} c
left join en_names e using (indicator_code)
left join {{ ref('stg_wb_indicator_meta') }} m using (indicator_code)
