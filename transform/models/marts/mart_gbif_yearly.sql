-- Biodiversité au Bénin (GBIF) : occurrences par année d'observation, jeux publiés
-- par des organismes béninois par année d'enregistrement.
select
    metric || '|' || year as gbif_id,
    metric,
    year,
    value,
    ingested_at
from {{ ref('stg_gbif_yearly') }}
