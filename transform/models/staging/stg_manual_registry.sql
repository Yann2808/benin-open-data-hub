select
    table_name,
    file,
    source_url,
    producer,
    try_cast(nullif(downloaded_on, '') as date) as downloaded_on,
    try_cast(row_count as integer)              as row_count,
    try_cast(loaded_at as timestamptz)          as loaded_at
from {{ source('raw', 'manual_registry') }}
