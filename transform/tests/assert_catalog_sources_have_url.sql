-- Toute source référencée ou jeu HDX du catalogue doit avoir un lien vers la source.
select kind, source, title
from {{ ref('mart_data_catalog') }}
where (kind = 'source référencée' or source like 'HDX — %')
  and url is null
