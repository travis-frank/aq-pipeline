{#
  stg_air_quality — flatten raw OpenAQ pulls to one row per measurement.

  Cleaning decisions:
  - measured_at is period.datetime_to (UTC). OpenAQ timestamps mark the END of
    a measurement interval, not the start; using datetime_from would shift
    daily aggregations by one period.
  - Flags are joined by time overlap (measurement period vs. flag window), not
    dropped. is_flagged is true when any OpenAQ flag overlaps; flag_reason is
    the concatenated flagType.label values (plus note when present). Readings
    without overlapping flags stay in the model with is_flagged = false.
  - Null values are kept (value is nullable). Sensors with an empty
    measurements array contribute zero rows — that is absence of data, not a
    silent filter on existing measurements.
  - Measurement coordinates are null for stationary monitors; we fall back to
    the location's coordinates rather than leaving lat/lon null.
  - Units are taken from the measurement's parameter object (sensor parameter
    as fallback). Spot-checked against current pulls: each parameter has a
    single unit (ppm for gases, µg/m³ for pm25/pm10) — no mixed-unit
    remapping applied. units_mixed_in_source is true if the same parameter
    appears with more than one unit inside a pull (should stay false).
  - Coverage fields (expected/observed counts, percent_coverage) are passed
    through for the marts layer; they are independent of flags.
#}

with pulls as (
    select
        id as pull_id,
        location_id,
        pulled_at,
        raw_json
    from {{ source('raw', 'openaq_pulls') }}
),

sensors as (
    select
        p.pull_id,
        p.location_id,
        p.pulled_at,
        p.raw_json -> 'location' ->> 'name' as location_name,
        (p.raw_json -> 'location' -> 'coordinates' ->> 'latitude')::double precision
            as location_latitude,
        (p.raw_json -> 'location' -> 'coordinates' ->> 'longitude')::double precision
            as location_longitude,
        sensor_elem as sensor_json
    from pulls p
    cross join lateral jsonb_array_elements(
        coalesce(p.raw_json -> 'sensors', '[]'::jsonb)
    ) as sensor_elem
),

measurements as (
    select
        s.pull_id,
        s.location_id,
        s.pulled_at,
        s.location_name,
        s.location_latitude,
        s.location_longitude,
        (s.sensor_json ->> 'id')::bigint as sensor_id,
        s.sensor_json ->> 'name' as sensor_name,
        coalesce(
            meas -> 'parameter' ->> 'name',
            s.sensor_json -> 'parameter' ->> 'name'
        ) as parameter,
        coalesce(
            meas -> 'parameter' ->> 'units',
            s.sensor_json -> 'parameter' ->> 'units'
        ) as units,
        (meas ->> 'value')::double precision as value,
        (meas -> 'period' -> 'datetime_from' ->> 'utc')::timestamptz as period_start,
        (meas -> 'period' -> 'datetime_to' ->> 'utc')::timestamptz as measured_at,
        coalesce(
            (meas -> 'coordinates' ->> 'latitude')::double precision,
            s.location_latitude
        ) as latitude,
        coalesce(
            (meas -> 'coordinates' ->> 'longitude')::double precision,
            s.location_longitude
        ) as longitude,
        (meas -> 'coverage' ->> 'expected_count')::integer as coverage_expected_count,
        (meas -> 'coverage' ->> 'observed_count')::integer as coverage_observed_count,
        (meas -> 'coverage' ->> 'percent_coverage')::double precision as coverage_pct
    from sensors s
    cross join lateral jsonb_array_elements(
        coalesce(s.sensor_json -> 'measurements' -> 'results', '[]'::jsonb)
    ) as meas
),

flags as (
    select
        s.pull_id,
        (s.sensor_json ->> 'id')::bigint as sensor_id,
        -- API returns camelCase; tolerate snake_case if serialization changes.
        coalesce(
            flag -> 'flagType' ->> 'label',
            flag -> 'flag_type' ->> 'label',
            flag -> 'flagType' ->> 'name',
            flag -> 'flag_type' ->> 'name'
        ) as flag_label,
        coalesce(flag ->> 'note', flag ->> 'Note') as flag_note,
        coalesce(
            (flag -> 'datetimeFrom' ->> 'utc')::timestamptz,
            (flag -> 'datetime_from' ->> 'utc')::timestamptz
        ) as flag_from,
        coalesce(
            (flag -> 'datetimeTo' ->> 'utc')::timestamptz,
            (flag -> 'datetime_to' ->> 'utc')::timestamptz
        ) as flag_to
    from sensors s
    cross join lateral jsonb_array_elements(
        coalesce(s.sensor_json -> 'flags' -> 'results', '[]'::jsonb)
    ) as flag
),

flagged as (
    select
        m.pull_id,
        m.sensor_id,
        m.measured_at,
        m.period_start,
        true as is_flagged,
        string_agg(reason, '; ' order by reason)
            filter (where reason is not null) as flag_reason
    from measurements m
    inner join flags f
        on f.pull_id = m.pull_id
        and f.sensor_id = m.sensor_id
        and f.flag_from is not null
        and f.flag_to is not null
        and m.period_start < f.flag_to
        and m.measured_at > f.flag_from
    cross join lateral (
        select nullif(
            trim(concat_ws(' — ', f.flag_label, nullif(f.flag_note, ''))),
            ''
        ) as reason
    ) r
    group by m.pull_id, m.sensor_id, m.measured_at, m.period_start
),

units_check as (
    select
        pull_id,
        parameter,
        count(distinct units) > 1 as units_mixed_in_source
    from measurements
    where parameter is not null
    group by pull_id, parameter
)

select
    m.pull_id,
    m.location_id,
    m.location_name,
    m.sensor_id,
    m.sensor_name,
    m.parameter,
    m.units,
    coalesce(u.units_mixed_in_source, false) as units_mixed_in_source,
    m.value,
    m.period_start,
    m.measured_at,
    m.latitude,
    m.longitude,
    coalesce(f.is_flagged, false) as is_flagged,
    f.flag_reason,
    m.coverage_expected_count,
    m.coverage_observed_count,
    m.coverage_pct,
    m.pulled_at
from measurements m
left join flagged f
    on f.pull_id = m.pull_id
    and f.sensor_id = m.sensor_id
    and f.measured_at is not distinct from m.measured_at
    and f.period_start is not distinct from m.period_start
left join units_check u
    on u.pull_id = m.pull_id
    and u.parameter = m.parameter
