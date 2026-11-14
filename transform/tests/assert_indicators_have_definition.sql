-- Chaque indicateur collecté pour de vrai doit avoir sa définition : officielle, ou rédigée par le hub
-- quand l'API n'en publie pas (WGI).
-- Avertissement seulement : une panne de l'API de métadonnées ne doit pas bloquer la publication.
{{ config(severity = 'warn') }}

select indicator_code, label_fr
from {{ ref('dim_indicator') }}
where source_published_on is not null
  and definition is null
  and definition_fr is null
