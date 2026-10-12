-- Inventaire du portail Open Data for Africa — Bénin, avec fraîcheur et couverture.
-- Sert à répondre à : quels jeux existent, de qui, à jour ou non, collectés ou non ?
with coverage as (
    select
        dataset_id,
        count(*)                    as n_values,
        count(distinct series_key)  as n_series,
        min(year)                   as first_year,
        max(year)                   as last_year
    from {{ ref('stg_odfa_observations') }}
    group by 1
)

select
    d.dataset_id,
    d.title,
    d.category,
    d.source_name,
    d.source_verified,
    d.license,
    d.terms_url,
    d.publication_date,
    d.last_updated_on,
    date_diff('day', d.last_updated_on::date, current_date) as days_since_update,
    c.first_year,
    c.last_year,
    coalesce(c.n_series, 0) as n_series,
    coalesce(c.n_values, 0) as n_values,
    coalesce(d.fetch_status, 'non collecté') as fetch_status,
    d.fetch_error,
    d.fetched_at,
    d.url
from {{ ref('stg_odfa_datasets') }} d
left join coverage c using (dataset_id)
