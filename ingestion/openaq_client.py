"""Pull recent OpenAQ measurements and flags into raw JSON files on disk."""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from openaq import OpenAQ
from openaq.core.exceptions import APIError, OpenAQError

logger = logging.getLogger(__name__)

INGESTION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = INGESTION_DIR.parent
DEFAULT_CONFIG_PATH = INGESTION_DIR / "locations.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"
PAGE_LIMIT = 1000


@dataclass
class SensorPullStats:
    sensor_id: int
    sensor_name: str
    measurement_count: int = 0
    flag_count: int = 0
    error: str | None = None


@dataclass
class LocationPullStats:
    location_id: int
    location_name: str | None = None
    output_file: str | None = None
    sensors: list[SensorPullStats] = field(default_factory=list)
    error: str | None = None


@dataclass
class PullSummary:
    locations_attempted: int = 0
    locations_pulled: int = 0
    locations: list[LocationPullStats] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def dataclass_to_dict(obj: Any) -> Any:
    """Recursively convert SDK dataclasses into JSON-serializable structures."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {key: dataclass_to_dict(value) for key, value in asdict(obj).items()}
    if isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]
    if isinstance(obj, tuple):
        return [dataclass_to_dict(item) for item in obj]
    return obj


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load ingestion config from JSON."""
    with config_path.open(encoding="utf-8") as config_file:
        config = json.load(config_file)

    location_ids = config.get("location_ids")
    if not isinstance(location_ids, list) or not location_ids:
        raise ValueError("Config must include a non-empty 'location_ids' list")

    return config


def _paginated_resource(
    fetch_page: Any,
) -> dict[str, Any]:
    """Collect all pages from a paginated SDK list call."""
    all_results: list[Any] = []
    meta: Any = None
    page = 1

    while True:
        response = fetch_page(page)
        if meta is None:
            meta = response.meta

        all_results.extend(response.results)

        if not response.results or page * response.meta.limit >= response.meta.found:
            break
        page += 1

    return {
        "meta": dataclass_to_dict(meta) if meta is not None else None,
        "results": [dataclass_to_dict(result) for result in all_results],
    }


def fetch_measurements(
    client: OpenAQ,
    sensor_id: int,
    lookback_days: int,
) -> dict[str, Any]:
    """Fetch raw measurements for a sensor over a recent time window."""
    datetime_to = datetime.now(timezone.utc).replace(microsecond=0)
    datetime_from = datetime_to - timedelta(days=lookback_days)

    return _paginated_resource(
        lambda page: client.measurements.list(
            sensors_id=sensor_id,
            data="measurements",
            datetime_from=datetime_from,
            datetime_to=datetime_to,
            page=page,
            limit=PAGE_LIMIT,
        )
    )


def fetch_sensor_flags(
    client: OpenAQ,
    sensor_id: int,
    lookback_days: int,
) -> dict[str, Any]:
    """Fetch OpenAQ data-quality flags for a sensor.

    The OpenAQ Python SDK does not yet expose a first-class flags resource.
    This uses the client's authenticated transport so rate limiting and error
    handling stay within the SDK.
    """
    datetime_to = datetime.now(timezone.utc).replace(microsecond=0)
    datetime_from = datetime_to - timedelta(days=lookback_days)

    all_results: list[Any] = []
    meta: dict[str, Any] | None = None
    page = 1

    while True:
        response = client._get(
            f"/sensors/{sensor_id}/flags",
            params={
                "page": page,
                "limit": PAGE_LIMIT,
                "datetime_from": datetime_from.isoformat(),
                "datetime_to": datetime_to.isoformat(),
            },
        )
        payload = response.json()
        if meta is None:
            meta = payload.get("meta")

        page_results = payload.get("results", [])
        all_results.extend(page_results)

        limit = (meta or {}).get("limit", PAGE_LIMIT)
        found = (meta or {}).get("found", len(page_results))
        if not page_results or page * limit >= found:
            break
        page += 1

    return {"meta": meta, "results": all_results}


def pull_location(
    client: OpenAQ,
    location_id: int,
    output_dir: Path,
    measurement_lookback_days: int,
    flags_lookback_days: int,
) -> LocationPullStats:
    """Pull one location and write a raw JSON file."""
    stats = LocationPullStats(location_id=location_id)

    try:
        location_response = client.locations.get(location_id)
    except OpenAQError as exc:
        message = f"Location {location_id}: failed to fetch location ({exc})"
        logger.error(message)
        stats.error = str(exc)
        return stats

    if not location_response.results:
        message = f"Location {location_id}: no location data returned"
        logger.warning(message)
        stats.error = message
        return stats

    location = location_response.results[0]
    stats.location_name = location.name
    sensors = location.sensors or []

    if not sensors:
        logger.warning("Location %s (%s): no sensors found", location_id, location.name)

    sensor_payloads: list[dict[str, Any]] = []

    for sensor in sensors:
        sensor_stats = SensorPullStats(
            sensor_id=sensor.id,
            sensor_name=sensor.name,
        )

        sensor_payload = dataclass_to_dict(sensor)
        sensor_payload["measurements"] = {"meta": None, "results": []}
        sensor_payload["flags"] = {"meta": None, "results": []}

        try:
            measurements = fetch_measurements(
                client,
                sensor.id,
                measurement_lookback_days,
            )
            sensor_payload["measurements"] = measurements
            sensor_stats.measurement_count = len(measurements["results"])
            if sensor_stats.measurement_count == 0:
                logger.info(
                    "Location %s sensor %s (%s): no measurements in lookback window",
                    location_id,
                    sensor.id,
                    sensor.name,
                )
        except (OpenAQError, APIError) as exc:
            message = (
                f"Location {location_id} sensor {sensor.id}: "
                f"failed to fetch measurements ({exc})"
            )
            logger.error(message)
            sensor_stats.error = str(exc)

        try:
            flags = fetch_sensor_flags(client, sensor.id, flags_lookback_days)
            sensor_payload["flags"] = flags
            sensor_stats.flag_count = len(flags["results"])
            if sensor_stats.flag_count == 0:
                logger.info(
                    "Location %s sensor %s (%s): no flags in lookback window",
                    location_id,
                    sensor.id,
                    sensor.name,
                )
        except (OpenAQError, APIError) as exc:
            message = (
                f"Location {location_id} sensor {sensor.id}: "
                f"failed to fetch flags ({exc})"
            )
            logger.error(message)
            sensor_stats.error = sensor_stats.error or str(exc)

        sensor_payloads.append(sensor_payload)
        stats.sensors.append(sensor_stats)

    pulled_at = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp = pulled_at.strftime("%Y%m%dT%H%M%SZ")
    location_dir = output_dir / str(location_id)
    location_dir.mkdir(parents=True, exist_ok=True)
    output_path = location_dir / f"{timestamp}.json"

    payload = {
        "pulled_at": pulled_at.isoformat(),
        "location_id": location_id,
        "location": dataclass_to_dict(location),
        "sensors": sensor_payloads,
    }

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, indent=2)
        output_file.write("\n")

    stats.output_file = str(output_path)
    logger.info("Wrote raw pull for location %s to %s", location_id, output_path)
    return stats


def run_ingestion(
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> PullSummary:
    """Run ingestion for all configured locations."""
    api_key = os.environ.get("OPENAQ_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAQ_API_KEY environment variable is not set")

    config = load_config(config_path)
    location_ids = config["location_ids"]
    measurement_lookback_days = int(config.get("measurement_lookback_days", 7))
    flags_lookback_days = int(config.get("flags_lookback_days", 30))

    summary = PullSummary(locations_attempted=len(location_ids))
    client = OpenAQ(api_key=api_key)

    try:
        for location_id in location_ids:
            try:
                location_stats = pull_location(
                    client,
                    int(location_id),
                    output_dir,
                    measurement_lookback_days,
                    flags_lookback_days,
                )
            except (OpenAQError, APIError) as exc:
                message = f"Location {location_id}: unexpected error ({exc})"
                logger.exception(message)
                summary.errors.append(message)
                summary.locations.append(
                    LocationPullStats(location_id=int(location_id), error=str(exc))
                )
                continue

            summary.locations.append(location_stats)
            if location_stats.error:
                summary.errors.append(
                    f"Location {location_id}: {location_stats.error}"
                )
            else:
                summary.locations_pulled += 1
    finally:
        client.close()

    return summary


def print_summary(summary: PullSummary) -> None:
    """Print a human-readable ingestion summary."""
    print(f"Locations attempted: {summary.locations_attempted}")
    print(f"Locations pulled:  {summary.locations_pulled}")
    print()

    for location in summary.locations:
        label = location.location_name or "unknown"
        print(f"Location {location.location_id} ({label})")

        if location.error:
            print(f"  error: {location.error}")
            continue

        if location.output_file:
            print(f"  output: {location.output_file}")

        print(f"  sensors: {len(location.sensors)}")
        for sensor in location.sensors:
            line = (
                f"    - sensor {sensor.sensor_id} ({sensor.sensor_name}): "
                f"{sensor.measurement_count} measurements, "
                f"{sensor.flag_count} flags"
            )
            if sensor.error:
                line += f" [error: {sensor.error}]"
            print(line)
        print()

    if summary.errors:
        print("Errors:")
        for error in summary.errors:
            print(f"  - {error}")
    else:
        print("Errors: none")


def main() -> int:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        summary = run_ingestion()
    except (RuntimeError, ValueError, OpenAQError, APIError) as exc:
        logger.error("%s", exc)
        return 1

    print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
