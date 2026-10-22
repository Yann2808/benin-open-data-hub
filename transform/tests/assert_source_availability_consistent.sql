-- Baromètre cohérent : taux entre 0 et 1, dernière réussite jamais postérieure
-- au dernier test, et une source joignable a forcément une dernière réussite.
select *
from {{ ref('mart_source_availability') }}
where availability_rate < 0
   or availability_rate > 1
   or n_reachable > n_tests
   or last_success_at > last_tested_at
   or (reachability = 'joignable' and last_success_at is distinct from last_tested_at)
