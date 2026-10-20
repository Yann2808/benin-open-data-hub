-- Disponibilité de chaque source : dernier statut, taux de disponibilité sur
-- l'historique, dernière réponse réussie. Sert à distinguer une source
-- inaccessible (elle ne répond pas) d'une donnée absente (elle répond, sans valeur).
with ranked as (
    select
        *,
        row_number() over (partition by source order by tested_at desc) as rn
    from {{ ref('stg_source_health') }}
),

history as (
    select
        source,
        count(*)                                        as n_tests,
        count(*) filter (where is_reachable)            as n_reachable,
        avg(is_reachable::integer)                      as availability_rate,
        min(tested_at)                                  as first_tested_at,
        max(tested_at) filter (where is_reachable)      as last_success_at,
        median(response_time_ms) filter (where is_reachable) as median_response_time_ms
    from {{ ref('stg_source_health') }}
    group by 1
)

select
    l.source,
    l.url_tested,
    l.official_api,
    l.license,
    l.collection_policy,
    l.tested_at                                         as last_tested_at,
    l.http_status                                       as last_http_status,
    l.response_time_ms                                  as last_response_time_ms,
    l.error_message                                     as last_error,
    case when l.is_reachable then 'joignable' else 'en panne' end as reachability,
    -- Badge affiché : une collecte interdite prime sur l'état du serveur
    case
        when l.collection_policy = 'interdite' then 'collecte interdite'
        when l.is_reachable then 'joignable'
        else 'en panne'
    end                                                 as badge,
    h.n_tests,
    h.n_reachable,
    h.availability_rate,
    h.first_tested_at,
    h.last_success_at,
    h.median_response_time_ms
from ranked l
join history h using (source)
where l.rn = 1
