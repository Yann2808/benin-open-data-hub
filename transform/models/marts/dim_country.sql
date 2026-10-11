-- Pays présents dans les données, avec libellé français (seed) et repli sur l'anglais.
with observed as (
    select distinct country_iso3, country_name_en
    from {{ ref('stg_wb_observations') }}
)

select
    o.country_iso3,
    coalesce(c.country_name_fr, o.country_name_en) as country_name_fr,
    o.country_name_en,
    c.region_fr,
    coalesce(c.is_uemoa, false)                     as is_uemoa,
    o.country_iso3 = '{{ var("focus_country") }}'   as is_focus
from observed o
left join {{ ref('countries') }} c using (country_iso3)
