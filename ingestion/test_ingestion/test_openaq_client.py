"""Unit tests for OpenAQ ingestion — mock the SDK, never hit the real API."""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from openaq.core.exceptions import HTTPRateLimitError, NotFoundError, RateLimitError

INGESTION_DIR = Path(__file__).resolve().parents[1]
if str(INGESTION_DIR) not in sys.path:
    sys.path.insert(0, str(INGESTION_DIR))

import openaq_client  # noqa: E402


@dataclass
class FakeMeta:
    name: str = "openaq-api"
    website: str = "/"
    page: int = 1
    limit: int = 1000
    found: int = 0


@dataclass
class FakeParameter:
    id: int
    name: str
    units: str
    display_name: str | None = None


@dataclass
class FakeSensor:
    id: int
    name: str
    parameter: FakeParameter


@dataclass
class FakeLocation:
    id: int
    name: str
    sensors: list[FakeSensor] = field(default_factory=list)


def _location_response(location: FakeLocation | None) -> MagicMock:
    response = MagicMock()
    response.results = [] if location is None else [location]
    return response


def _measurements_response(results: list[dict]) -> MagicMock:
    response = MagicMock()
    response.meta = FakeMeta(found=len(results), limit=1000)
    response.results = results
    return response


def _flags_response(results: list[dict]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {
        "meta": {"page": 1, "limit": 1000, "found": len(results)},
        "results": results,
    }
    return response


def _mock_client(
    location: FakeLocation | None,
    measurements_by_sensor: dict[int, list[dict]] | None = None,
    flags_by_sensor: dict[int, list[dict]] | None = None,
) -> MagicMock:
    client = MagicMock()
    client.locations.get.return_value = _location_response(location)

    measurements_by_sensor = measurements_by_sensor or {}
    flags_by_sensor = flags_by_sensor or {}

    def list_measurements(*, sensors_id: int, **_kwargs):
        return _measurements_response(measurements_by_sensor.get(sensors_id, []))

    def get_flags(path: str, **_kwargs):
        sensor_id = int(path.split("/")[2])
        return _flags_response(flags_by_sensor.get(sensor_id, []))

    client.measurements.list.side_effect = list_measurements
    client._get.side_effect = get_flags
    return client


PM25 = FakeParameter(id=2, name="pm25", units="µg/m³", display_name="PM2.5")
O3 = FakeParameter(id=3, name="o3", units="ppm", display_name="O3")


def test_multiple_sensors_written_with_full_structure(tmp_path: Path) -> None:
    location = FakeLocation(
        id=100,
        name="Downtown",
        sensors=[
            FakeSensor(id=11, name="PM2.5", parameter=PM25),
            FakeSensor(id=12, name="O3", parameter=O3),
        ],
    )
    measurements = {
        11: [{"value": 8.1, "parameter": {"name": "pm25"}}],
        12: [
            {"value": 0.03, "parameter": {"name": "o3"}},
            {"value": 0.04, "parameter": {"name": "o3"}},
        ],
    }
    flags = {11: [{"flagType": "questionable"}], 12: []}
    client = _mock_client(location, measurements, flags)

    stats = openaq_client.pull_location(client, 100, tmp_path, 7, 30)

    assert stats.error is None
    assert stats.output_file is not None
    payload = json.loads(Path(stats.output_file).read_text(encoding="utf-8"))

    assert payload["location_id"] == 100
    assert payload["location"]["id"] == 100
    assert payload["location"]["name"] == "Downtown"
    assert len(payload["sensors"]) == 2

    by_id = {sensor["id"]: sensor for sensor in payload["sensors"]}
    assert set(by_id) == {11, 12}

    pm = by_id[11]
    assert pm["name"] == "PM2.5"
    assert pm["parameter"]["name"] == "pm25"
    assert len(pm["measurements"]["results"]) == 1
    assert pm["measurements"]["results"][0]["value"] == 8.1
    assert len(pm["flags"]["results"]) == 1

    o3 = by_id[12]
    assert o3["name"] == "O3"
    assert len(o3["measurements"]["results"]) == 2
    assert o3["flags"]["results"] == []

    assert [s.measurement_count for s in stats.sensors] == [1, 2]
    client.locations.get.assert_called_once_with(100)
    assert client.measurements.list.call_count == 2


def test_zero_sensors_does_not_raise(tmp_path: Path) -> None:
    location = FakeLocation(id=200, name="Empty Station", sensors=[])
    client = _mock_client(location)

    stats = openaq_client.pull_location(client, 200, tmp_path, 7, 30)

    assert stats.error is None
    assert stats.sensors == []
    payload = json.loads(Path(stats.output_file).read_text(encoding="utf-8"))
    assert payload["sensors"] == []
    client.measurements.list.assert_not_called()


def test_empty_measurements_does_not_raise(tmp_path: Path) -> None:
    location = FakeLocation(
        id=201,
        name="Quiet Station",
        sensors=[FakeSensor(id=21, name="PM2.5", parameter=PM25)],
    )
    client = _mock_client(location, measurements_by_sensor={21: []}, flags_by_sensor={21: []})

    stats = openaq_client.pull_location(client, 201, tmp_path, 7, 30)

    assert stats.error is None
    assert stats.sensors[0].measurement_count == 0
    assert stats.sensors[0].flag_count == 0
    payload = json.loads(Path(stats.output_file).read_text(encoding="utf-8"))
    assert payload["sensors"][0]["measurements"]["results"] == []
    assert payload["sensors"][0]["flags"]["results"] == []


@pytest.mark.parametrize(
    "exc",
    [
        NotFoundError("location not found"),
        RateLimitError("rate limit exceeded"),
        HTTPRateLimitError("HTTP 429"),
    ],
)
def test_sdk_error_on_location_is_caught_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, exc: Exception
) -> None:
    client = MagicMock()
    client.locations.get.side_effect = exc

    with caplog.at_level(logging.ERROR):
        stats = openaq_client.pull_location(client, 404, tmp_path, 7, 30)

    assert stats.error == str(exc)
    assert stats.output_file is None
    assert any("failed to fetch location" in record.message for record in caplog.records)
    assert not list(tmp_path.iterdir())


def test_rate_limit_on_measurements_is_caught_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    location = FakeLocation(
        id=300,
        name="Limited",
        sensors=[FakeSensor(id=31, name="PM2.5", parameter=PM25)],
    )
    client = _mock_client(location)
    client.measurements.list.side_effect = HTTPRateLimitError("too many requests")

    with caplog.at_level(logging.ERROR):
        stats = openaq_client.pull_location(client, 300, tmp_path, 7, 30)

    assert stats.error is None
    assert stats.output_file is not None
    assert "too many requests" in (stats.sensors[0].error or "")
    assert any("failed to fetch measurements" in record.message for record in caplog.records)
    payload = json.loads(Path(stats.output_file).read_text(encoding="utf-8"))
    assert payload["sensors"][0]["measurements"]["results"] == []


def test_run_ingestion_not_found_does_not_crash(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    config_path = tmp_path / "locations.json"
    config_path.write_text(
        json.dumps({"location_ids": [999], "measurement_lookback_days": 1, "flags_lookback_days": 1}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "raw"

    mock_client = MagicMock()
    mock_client.locations.get.side_effect = NotFoundError("not found")

    with (
        patch.dict("os.environ", {"OPENAQ_API_KEY": "a" * 64}),
        patch("openaq_client.OpenAQ", return_value=mock_client),
        caplog.at_level(logging.ERROR),
    ):
        summary = openaq_client.run_ingestion(config_path=config_path, output_dir=output_dir)

    assert summary.locations_attempted == 1
    assert summary.locations_pulled == 0
    assert summary.errors
    mock_client.close.assert_called_once()
    assert not list(output_dir.glob("**/*.json"))
