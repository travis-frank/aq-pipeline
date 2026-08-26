-- Assert mart min/max/avg match staging recomputed from unflagged rows only.
-- Fails if flagged readings are silently included in those aggregates.

with expected as (
    select
        location_id,
        (measured_at at time zone 'UTC')::date as measurement_date,
        parameter,
        min(value) filter (where not is_flagged) as min_value,
        max(value) filter (where not is_flagged) as max_value,
        avg(value) filter (where not is_flagged) as avg_value,
        count(*) filter (where is_flagged) as flagged_count
    from {{ ref('stg_air_quality') }}
    group by 1, 2, 3
),

mismatches as (
    select
        m.location_id,
        m.measurement_date,
        m.parameter,
        m.min_value as mart_min,
        e.min_value as expected_min,
        m.max_value as mart_max,
        e.max_value as expected_max,
        m.avg_value as mart_avg,
        e.avg_value as expected_avg,
        m.flagged_count as mart_flagged,
        e.flagged_count as expected_flagged
    from {{ ref('mart_station_daily') }} m
    inner join expected e
        on e.location_id = m.location_id
        and e.measurement_date = m.measurement_date
        and e.parameter = m.parameter
    where m.min_value is distinct from e.min_value
       or m.max_value is distinct from e.max_value
       or m.flagged_count is distinct from e.flagged_count
       or (
            m.avg_value is distinct from e.avg_value
            and (
                m.avg_value is null
                or e.avg_value is null
                or abs(m.avg_value - e.avg_value) > 1e-9
            )
       )
)

select *
from mismatches
