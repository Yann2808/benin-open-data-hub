-- Agrégats annuels GBIF pour le Bénin.
select
    metric,
    try_cast(year as integer)               as year,
    try_cast(value as bigint)               as value,
    try_cast(ingested_at as timestamptz)    as ingested_at
from {{ source('raw', 'gbif_yearly') }}
where try_cast(year as integer) is not null
