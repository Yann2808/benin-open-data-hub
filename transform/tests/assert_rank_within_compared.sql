-- Le rang du Bénin doit être compris entre 1 et le nombre de pays comparés.
select *
from {{ ref('mart_benin_scorecard') }}
where rank_among_peers is not null
  and (rank_among_peers < 1 or rank_among_peers > n_countries_compared)
