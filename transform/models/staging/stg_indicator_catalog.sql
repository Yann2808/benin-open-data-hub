select
    indicator_code,
    label_fr,
    theme,
    unit_fr,
    try_cast(higher_is_better as boolean) as higher_is_better
from {{ source('raw', 'wb_indicator_catalog') }}
