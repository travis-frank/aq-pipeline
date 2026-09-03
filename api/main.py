"""FastAPI service over the air-quality warehouse."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from fastapi import FastAPI, Response, status

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"

app = FastAPI(title="aq-pipeline API", version="0.1.0")


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
    """Connect using DB_* variables."""
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


@app.on_event("startup")
def startup() -> None:
    load_dotenv()


@app.get("/health")
def health(response: Response) -> dict[str, str]:
    """Confirm the API can reach the warehouse Postgres."""
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except (RuntimeError, psycopg2.Error) as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "database": str(exc)}

    return {"status": "ok", "database": "connected"}
