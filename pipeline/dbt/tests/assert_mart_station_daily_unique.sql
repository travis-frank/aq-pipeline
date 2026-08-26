-- Grain of mart_station_daily must be unique on
-- (location_id, measurement_date, parameter).

select
    location_id,
    measurement_date,
    parameter,
    count(*) as row_count
from {{ ref('mart_station_daily') }}
group by
    location_id,
    measurement_date,
    parameter
having count(*) > 1
