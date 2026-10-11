select
    study_id,
    idno,
    title,
    nation,
    try_cast(year_start as integer)        as year_start,
    try_cast(year_end as integer)          as year_end,
    repository,
    data_access_type,
    try_cast(created as date)              as created_on,
    try_cast(changed as date)              as changed_on,
    url,
    starts_with(coalesce(idno, ''), 'DEMO-') as is_demo,
    try_cast(ingested_at as timestamptz)   as ingested_at
from {{ source('raw', 'nada_studies') }}
where study_id is not null
