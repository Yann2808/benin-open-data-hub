-- Sources seulement cataloguées (aucune collecte), issues de config/sources.yml.
select title, producer, topic, url, access, status
from {{ source('raw', 'catalog_sources') }}
where title is not null
