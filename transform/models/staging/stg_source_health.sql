-- Tests d'accès aux sources, typés. Joignable = réponse HTTP 2xx ou 3xx.
select
    source,
    url_tested,
    try_cast(http_status as integer)                        as http_status,
    try_cast(response_time_ms as integer)                   as response_time_ms,
    coalesce(try_cast(official_api as boolean), false)      as official_api,
    license,
    collection_policy,
    try_cast(tested_at as timestamptz)                      as tested_at,
    error_message,
    coalesce(try_cast(http_status as integer) between 200 and 399, false) as is_reachable
from {{ source('raw', 'source_health') }}
where source is not null and try_cast(tested_at as timestamptz) is not null
