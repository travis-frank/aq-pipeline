"""Raw pull storage: local disk or S3, selected via environment variables.

Env contract (swap for local vs AWS — no code changes):
  S3_BUCKET      — if set, read/write S3; if unset, use local files
  S3_PREFIX      — key prefix inside the bucket (default: raw)
  RAW_DATA_DIR   — local directory (default: <repo>/data/raw)
  AWS_DEFAULT_REGION / AWS_REGION — used by boto3 when S3_BUCKET is set
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

INGESTION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = INGESTION_DIR.parent
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"


def raw_data_dir() -> Path:
    return Path(os.environ.get("RAW_DATA_DIR", str(DEFAULT_RAW_DIR)))


def s3_bucket() -> str | None:
    bucket = os.environ.get("S3_BUCKET", "").strip()
    return bucket or None


def s3_prefix() -> str:
    return os.environ.get("S3_PREFIX", "raw").strip().strip("/")


def _s3_client():
    import boto3

    return boto3.client("s3")


def write_raw_pull(
    location_id: int,
    pulled_at: datetime,
    payload: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> str:
    """Persist one pull; returns a URI (file path or s3://...)."""
    timestamp = pulled_at.strftime("%Y%m%dT%H%M%SZ")
    relative_key = f"{location_id}/{timestamp}.json"
    body = json.dumps(payload, indent=2) + "\n"

    bucket = s3_bucket()
    if bucket:
        key = f"{s3_prefix()}/{relative_key}" if s3_prefix() else relative_key
        _s3_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        uri = f"s3://{bucket}/{key}"
        logger.info("Wrote raw pull for location %s to %s", location_id, uri)
        return uri

    base = output_dir or raw_data_dir()
    path = base / relative_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    logger.info("Wrote raw pull for location %s to %s", location_id, path)
    return str(path)


def iter_raw_payloads(
    *,
    raw_dir: Path | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (source_uri, payload) for each raw pull object."""
    bucket = s3_bucket()
    if bucket:
        client = _s3_client()
        prefix = f"{s3_prefix()}/" if s3_prefix() else ""
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.endswith(".json"):
                    continue
                response = client.get_object(Bucket=bucket, Key=key)
                payload = json.loads(response["Body"].read().decode("utf-8"))
                yield f"s3://{bucket}/{key}", payload
        return

    base = raw_dir or raw_data_dir()
    if not base.is_dir():
        return
    for path in sorted(base.glob("*/*.json")):
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        yield str(path), payload
