-- Ouverture des statistiques officielles (ODIN) : Bénin et pays de comparaison,
-- avec le rang parmi les pays du hub pour chaque édition.
select
    s.country_iso3 || '|' || s.edition_year                         as odin_id,
    s.country_iso3,
    c.country_name_fr,
    c.is_focus,
    s.edition_year,
    s.overall_score,
    s.coverage_score,
    s.openness_score,
    s.rank_world,
    s.n_countries_ranked,
    rank() over (partition by s.edition_year order by s.overall_score desc) as rank_among_hub,
    count(*) over (partition by s.edition_year)                     as n_hub_countries,
    s.ingested_at
from {{ ref('stg_odin_scores') }} s
join {{ ref('dim_country') }} c using (country_iso3)
