-- Chaque indicateur collecté pour de vrai doit avoir sa définition officielle.
-- Avertissement seulement : une panne de l'API de métadonnées ne doit pas bloquer la publication.
{{ config(severity = 'warn') }}

select indicator_code, label_fr
from {{ ref('dim_indicator') }}
where source_published_on is not null
  and definition is null
