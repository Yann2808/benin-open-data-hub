-- Catalogue unifié de ce que le hub connaît sur le Bénin, toutes sources confondues.
-- C'est la brique « catalogue des données » : quoi, d'où, quelle période, quel lien.

select
    'indicateur'                               as kind,
    'World Bank (WDI)'                         as source,
    i.label_fr                                 as title,
    i.theme                                    as topic,
    min(f.year)                                as period_start,
    max(f.year)                                as period_end,
    i.source_url                               as url,
    'ouvert'                                   as access,
    bool_or(f.is_demo)                         as is_demo
from {{ ref('dim_indicator') }} i
left join {{ ref('fct_indicator_values') }} f
    on f.indicator_code = i.indicator_code
   and f.country_iso3 = '{{ var("focus_country") }}'
group by all

union all

select
    'enquête',
    'INStaD (catalogue NADA)',
    title,
    null,
    year_start,
    coalesce(year_end, year_start),
    url,
    coalesce(data_access_type, 'non précisé'),
    is_demo
from {{ ref('stg_nada_studies') }}

union all

select
    'fichier déposé',
    coalesce(producer, 'non précisé'),
    table_name,
    null,
    null,
    null,
    source_url,
    'ouvert',
    false
from {{ ref('stg_manual_registry') }}

union all

select
    'jeu de données',
    'Open Data for Africa — ' || coalesce(d.source_name, 'source non précisée'),
    d.title,
    d.category,
    min(o.year),
    max(o.year),
    d.url,
    coalesce(d.license, 'licence non précisée'),
    false
from {{ ref('stg_odfa_datasets') }} d
left join {{ ref('stg_odfa_observations') }} o using (dataset_id)
group by all
