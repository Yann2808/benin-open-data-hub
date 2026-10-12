-- Valeurs collectées sur Open Data for Africa, au format long.
-- `dimensions` est un objet JSON (les dimensions varient d'un jeu à l'autre).
select
    dataset_id,
    series_key,
    dimensions,
    nullif(frequency, '')                    as frequency,
    try_cast(date as date)                   as date,
    year(try_cast(date as date))             as year,
    try_cast(value as double)                as value,
    try_cast(fetched_at as timestamptz)      as fetched_at
from {{ source('raw', 'odfa_observations') }}
where try_cast(value as double) is not null
