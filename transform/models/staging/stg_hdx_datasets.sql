-- Catalogue HDX du Bénin. dataset_date a la forme « [2020-01-01T00:00:00 TO 2020-12-31T23:59:59] » :
-- on en tire les années de début et de fin.
select
    dataset_id,
    name,
    title,
    organization,
    license,
    try_cast(regexp_extract(dataset_date, '^\[?(\d{4})', 1) as integer)          as period_start,
    try_cast(regexp_extract(dataset_date, 'TO (\d{4})', 1) as integer)           as period_end,
    try_cast(last_modified as timestamp)                                          as last_modified,
    try_cast(num_resources as integer)                                            as num_resources,
    url
from {{ source('raw', 'hdx_datasets') }}
where dataset_id is not null
