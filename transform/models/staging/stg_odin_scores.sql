-- Scores ODIN typés ; une ligne par pays × édition (collecte la plus récente).
select * exclude (rn)
from (
    select
        upper(country_iso3)                         as country_iso3,
        try_cast(edition_year as integer)           as edition_year,
        try_cast(overall_score as double)           as overall_score,
        try_cast(coverage_score as double)          as coverage_score,
        try_cast(openness_score as double)          as openness_score,
        try_cast(rank_world as integer)             as rank_world,
        try_cast(n_countries_ranked as integer)     as n_countries_ranked,
        try_cast(ingested_at as timestamptz)        as ingested_at,
        row_number() over (
            partition by upper(country_iso3), edition_year order by ingested_at desc
        ) as rn
    from {{ source('raw', 'odin_scores') }}
    where country_iso3 is not null and try_cast(edition_year as integer) is not null
)
where rn = 1
