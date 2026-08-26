{#
  mart_station_daily — one row per station × UTC day × pollutant.

  Aggregation rules:
  - min_value / max_value / avg_value use ONLY unflagged readings
    (WHERE NOT is_flagged). Flagged OpenAQ QA readings are never folded into
    those stats; they are counted separately in flagged_count so they stay
    visible without polluting the aggregates.
  - record_count is all staging rows for the grain (flagged + unflagged).
  - coverage_pct = sum(coverage_observed_count) / sum(coverage_expected_count)
    × 100 from OpenAQ's per-measurement coverage fields (independent of flags).
  - measurement_date is the UTC calendar date of measured_at (period end).
#}

with staging as (
    select *
    from {{ ref('stg_air_quality') }}
)

select
    location_id,
    max(location_name) as location_name,
    (measured_at at time zone 'UTC')::date as measurement_date,
    parameter,
    max(units) as units,
    count(*) as record_count,
    count(*) filter (where is_flagged) as flagged_count,
    count(*) filter (where not is_flagged) as unflagged_count,
    min(value) filter (where not is_flagged) as min_value,
    max(value) filter (where not is_flagged) as max_value,
    avg(value) filter (where not is_flagged) as avg_value,
    case
        when coalesce(sum(coverage_expected_count), 0) = 0 then null
        else (
            sum(coverage_observed_count)::double precision
            / sum(coverage_expected_count)::double precision
        ) * 100.0
    end as coverage_pct,
    min(latitude) as latitude,
    min(longitude) as longitude,
    max(pulled_at) as last_pulled_at
from staging
group by
    location_id,
    (measured_at at time zone 'UTC')::date,
    parameter
