-- Tableau de bord du pays focus (Bénin) face à ses pairs.
-- Pour chaque indicateur : dernière valeur, évolution, médiane des pairs,
-- rang (quand l'indicateur a un sens de lecture) et position.
-- Seuls les pays dont la donnée est assez récente entrent dans la comparaison.
{% set focus = var('focus_country') %}
{% set window = var('comparison_window_years') %}

with lv as (
    select
        l.*,
        max(l.latest_year) over (partition by l.indicator_code) as indicator_max_year
    from {{ ref('mart_latest_values') }} l
),

comparable as (
    select *
    from lv
    where latest_year >= indicator_max_year - {{ window }}
),

ranked as (
    select
        c.*,
        i.higher_is_better,
        case
            when i.higher_is_better is null then null
            when i.higher_is_better then rank() over (partition by c.indicator_code order by c.latest_value desc)
            else rank() over (partition by c.indicator_code order by c.latest_value asc)
        end as rank_among_peers,
        count(*) over (partition by c.indicator_code) as n_countries_compared
    from comparable c
    inner join {{ ref('dim_indicator') }} i using (indicator_code)
),

peer_stats as (
    select
        indicator_code,
        median(latest_value) as peer_median,
        min(latest_value)    as peer_min,
        max(latest_value)    as peer_max
    from comparable
    where country_iso3 <> '{{ focus }}'
    group by 1
)

select
    i.indicator_code,
    i.label_fr,
    i.theme,
    i.unit_fr,
    i.higher_is_better,
    f.latest_year,
    f.latest_value,
    f.baseline_year,
    f.change_abs,
    f.change_pct,
    -- Pour un indicateur déjà en %, l'évolution se lit en points, pas en % relatif
    -- (passer de 2 % à 4 % de chômage = +2 points, pas +100 %).
    strpos(i.unit_fr, '%') > 0 as change_in_points,
    p.peer_median,
    p.peer_min,
    p.peer_max,
    r.rank_among_peers,
    r.n_countries_compared,
    case
        when f.latest_value is null or p.peer_median is null then 'données insuffisantes'
        when i.higher_is_better is null then
            case when f.latest_value >= p.peer_median then 'au-dessus de la médiane' else 'en dessous de la médiane' end
        when (f.latest_value >= p.peer_median) = i.higher_is_better then 'mieux que la médiane des pairs'
        else 'moins bien que la médiane des pairs'
    end as position_vs_peers,
    r.country_iso3 is null and f.latest_value is not null as is_stale,
    coalesce(f.is_demo, false) as is_demo
from {{ ref('dim_indicator') }} i
left join lv f
    on f.indicator_code = i.indicator_code and f.country_iso3 = '{{ focus }}'
left join ranked r
    on r.indicator_code = i.indicator_code and r.country_iso3 = '{{ focus }}'
left join peer_stats p
    on p.indicator_code = i.indicator_code
