"""Tests for local vs S3 raw storage selection via env."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

INGESTION_DIR = Path(__file__).resolve().parents[1]
if str(INGESTION_DIR) not in sys.path:
    sys.path.insert(0, str(INGESTION_DIR))

import raw_storage  # noqa: E402


def test_write_raw_pull_local(tmp_path, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    pulled_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    payload = {"location_id": 1, "pulled_at": pulled_at.isoformat()}

    uri = raw_storage.write_raw_pull(1, pulled_at, payload, output_dir=tmp_path)

    path = Path(uri)
    assert path.is_file()
    assert json.loads(path.read_text()) == payload


def test_write_raw_pull_s3(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_PREFIX", "raw")
    pulled_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    payload = {"location_id": 9, "pulled_at": pulled_at.isoformat()}

    client = MagicMock()
    with patch("raw_storage._s3_client", return_value=client):
        uri = raw_storage.write_raw_pull(9, pulled_at, payload)

    assert uri == "s3://test-bucket/raw/9/20240102T030405Z.json"
    client.put_object.assert_called_once()
    kwargs = client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Key"] == "raw/9/20240102T030405Z.json"


def test_iter_raw_payloads_local(tmp_path, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    loc_dir = tmp_path / "42"
    loc_dir.mkdir()
    payload = {"location_id": 42, "pulled_at": "2024-01-01T00:00:00+00:00"}
    (loc_dir / "x.json").write_text(json.dumps(payload), encoding="utf-8")

    items = list(raw_storage.iter_raw_payloads(raw_dir=tmp_path))
    assert len(items) == 1
    assert items[0][1] == payload
