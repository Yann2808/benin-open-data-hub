-- Dernière valeur disponible par indicateur × pays, et évolution sur N ans.
-- La valeur de référence est celle de l'année (dernière - N), ou à défaut
-- la plus proche avant elle : les séries africaines ont souvent des trous.
{% set n = var('trend_years') %}

with ranked as (
    select
        *,
        row_number() over (partition by indicator_code, country_iso3 order by year desc) as rn
    from {{ ref('fct_indicator_values') }}
),

latest as (
    select
        indicator_code, country_iso3, year as latest_year, value as latest_value, is_demo,
        collection_status, obs_status, source_last_updated
    from ranked
    where rn = 1
),

baseline as (
    select
        l.indicator_code,
        l.country_iso3,
        f.year  as baseline_year,
        f.value as baseline_value,
        row_number() over (partition by l.indicator_code, l.country_iso3 order by f.year desc) as rn
    from latest l
    inner join {{ ref('fct_indicator_values') }} f
        on f.indicator_code = l.indicator_code
       and f.country_iso3 = l.country_iso3
       and f.year <= l.latest_year - {{ n }}
)

select
    l.indicator_code || '|' || l.country_iso3 as latest_id,
    l.indicator_code,
    l.country_iso3,
    l.latest_year,
    l.latest_value,
    b.baseline_year,
    b.baseline_value,
    l.latest_value - b.baseline_value as change_abs,
    case
        when b.baseline_value is null or b.baseline_value = 0 then null
        else (l.latest_value - b.baseline_value) / abs(b.baseline_value)
    end as change_pct,
    l.is_demo,
    l.collection_status,
    l.obs_status,
    l.source_last_updated
from latest l
left join baseline b
    on b.indicator_code = l.indicator_code
   and b.country_iso3 = l.country_iso3
   and b.rn = 1
