-- Les indicateurs exprimés en % de la population doivent rester entre 0 et 100.
-- Un échec signale un changement d'unité côté source ou une erreur de parsing.
select f.*
from {{ ref('fct_indicator_values') }} f
inner join {{ ref('dim_indicator') }} i using (indicator_code)
where i.unit_fr like '% de la population%'
  and (f.value < 0 or f.value > 100)
