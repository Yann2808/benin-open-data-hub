-- Définition officielle de chaque indicateur, telle que publiée par la World Bank.
-- Une ligne par indicateur : la collecte la plus récente l'emporte.
select * exclude (rn)
from (
    select
        indicator_code,
        name_source,
        definition,
        source_organization,
        try_cast(ingested_at as timestamptz) as ingested_at,
        row_number() over (partition by indicator_code order by ingested_at desc) as rn
    from {{ source('raw', 'wb_indicator_meta') }}
    where indicator_code is not null
)
where rn = 1
