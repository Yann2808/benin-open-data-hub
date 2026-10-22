-- Typage et dédoublonnage des observations World Bank.
-- Si plusieurs ingestions se chevauchent, on garde la plus récente.
with typed as (
    select
        indicator_code,
        indicator_name                          as indicator_name_en,
        upper(country_iso3)                     as country_iso3,
        country_name                            as country_name_en,
        try_cast(year as integer)               as year,
        try_cast(value as double)               as value,
        obs_status,
        source_last_updated,
        source_last_updated = 'DEMO-SYNTHETIQUE' as is_demo,
        try_cast(ingested_at as timestamptz)    as ingested_at
    from {{ source('raw', 'wb_observations') }}
)

select * exclude (rn)
from (
    select
        *,
        row_number() over (
            partition by indicator_code, country_iso3, year
            order by ingested_at desc
        ) as rn
    from typed
    where year is not null
)
where rn = 1
