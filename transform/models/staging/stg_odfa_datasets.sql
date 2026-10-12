-- Catalogue du portail Open Data for Africa — Bénin.
select
    d.dataset_id,
    d.title,
    d.description,
    d.dataset_type,
    d.category,
    d.source_id,
    d.source_name,
    try_cast(d.source_verified as boolean)                  as source_verified,
    d.license,
    d.terms_url,
    try_cast(d.publication_date as timestamp)::date         as publication_date,
    try_cast(d.last_updated_on as timestamp)                as last_updated_on,
    try_cast(d.next_release_date as timestamp)::date        as next_release_date,
    d.dimensions,
    d.url,
    l.status                                                as fetch_status,
    try_cast(l.row_count as integer)                        as fetched_rows,
    l.error                                                 as fetch_error,
    try_cast(l.fetched_at as timestamptz)                   as fetched_at
from {{ source('raw', 'odfa_datasets') }} d
left join {{ source('raw', 'odfa_fetch_log') }} l using (dataset_id)
where d.dataset_id is not null
