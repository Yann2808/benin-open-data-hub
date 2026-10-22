-- Scores ODIN entre 0 et 100, rang parmi les pays du hub cohérent.
select *
from {{ ref('mart_odin_scores') }}
where overall_score not between 0 and 100
   or coverage_score not between 0 and 100
   or openness_score not between 0 and 100
   or rank_among_hub > n_hub_countries
