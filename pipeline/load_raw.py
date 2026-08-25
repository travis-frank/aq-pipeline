"""Load OpenAQ raw JSON files into Postgres as unmodified JSONB.

ELT decision: this loader does not flatten nested location / sensor /
measurement / flag structure. Each file from data/raw/ becomes one row with
the original JSON in a JSONB column. The raw layer is an unmodified landing
zone. All flattening and typing in the dbt staging model. That way
staging and marts can be rebuilt from scratch with `dbt run` without
re-pulling from the API.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
ENV_FILE = PROJECT_ROOT / ".env"

CREATE_SQL = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.openaq_pulls (
    id          bigserial PRIMARY KEY,
    location_id bigint NOT NULL,
    pulled_at   timestamptz NOT NULL,
    raw_json    jsonb NOT NULL,
    UNIQUE (location_id, pulled_at)
);
"""

UPSERT_SQL = """
INSERT INTO raw.openaq_pulls (location_id, pulled_at, raw_json)
VALUES (%s, %s, %s::jsonb)
ON CONFLICT (location_id, pulled_at)
DO UPDATE SET raw_json = EXCLUDED.raw_json;
"""


def load_dotenv(path: Path = ENV_FILE) -> None:
    """Load KEY=VALUE pairs from .env without overwriting existing env vars."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def db_connect():
    """Connect using the same DB_* variables as docker-compose."""
    required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing database env vars: {', '.join(missing)}")

    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def iter_raw_files(raw_dir: Path) -> list[Path]:
    """Return JSON pull files under data/raw/{location_id}/{timestamp}.json."""
    if not raw_dir.is_dir():
        return []
    return sorted(path for path in raw_dir.glob("*/*.json") if path.is_file())


def parse_pull(path: Path) -> tuple[int, datetime, dict[str, Any]]:
    """Read a pull file and return location_id, pulled_at, and the raw object."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object at the root")

    location_id = payload.get("location_id")
    pulled_at = payload.get("pulled_at")
    if location_id is None or not pulled_at:
        raise ValueError(f"{path}: missing location_id or pulled_at")

    return int(location_id), datetime.fromisoformat(pulled_at), payload


def load_raw(raw_dir: Path = DEFAULT_RAW_DIR) -> int:
    """Create the raw table if needed and upsert every pull file. Returns row count written."""
    files = iter_raw_files(raw_dir)
    if not files:
        logger.warning("No JSON files found under %s", raw_dir)
        return 0

    conn = db_connect()
    loaded = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_SQL)
                for path in files:
                    location_id, pulled_at, payload = parse_pull(path)
                    cur.execute(
                        UPSERT_SQL,
                        (location_id, pulled_at, json.dumps(payload)),
                    )
                    loaded += 1
                    logger.info(
                        "Loaded location %s pulled_at %s from %s",
                        location_id,
                        pulled_at.isoformat(),
                        path,
                    )
    finally:
        conn.close()

    return loaded


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv()
    try:
        loaded = load_raw()
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        logger.error("%s", exc)
        return 1

    print(f"Loaded {loaded} file(s) into raw.openaq_pulls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
