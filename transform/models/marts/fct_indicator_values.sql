-- Une ligne par indicateur × pays × année, uniquement les valeurs renseignées.
select
    o.indicator_code || '|' || o.country_iso3 || '|' || o.year as observation_id,
    o.indicator_code,
    o.country_iso3,
    o.year,
    o.value,
    o.is_demo,
    -- Statut de collecte : valeur collectée sur l'API, ou synthétique (make demo)
    case when o.is_demo then 'démo' else 'collectée' end as collection_status,
    o.obs_status,
    o.source_last_updated,
    o.ingested_at
from {{ ref('stg_wb_observations') }} o
inner join {{ ref('stg_indicator_catalog') }} using (indicator_code)
where o.value is not null
