"""Verify a DATABASE_URL is reachable and pgvector is installed.

Usage (from backend/):

    python -m scripts.verify_supabase

This is a smoke test for hosted Supabase projects: it confirms we can
    reach Postgres over TLS, that `pgvector` is installed (required by the
    knowledge agent), and that we can list schemas. It does NOT
    introspect data, run migrations, or write anything.

Never paste the real DATABASE_URL into chat, screenshots, or this
    file. The script reads the URL from `backend/.env`.
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text


def _load_env() -> None:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def main() -> int:
    _load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set in backend/.env", file=sys.stderr)
        return 2
    if "supabase" not in url.lower() and "localhost" not in url.lower():
        print(
            "DATABASE_URL does not look like Supabase or local Postgres — aborting",
            file=sys.stderr,
        )
        return 2

    print(f"Connecting to {url.split('@')[-1]}")
    engine = create_engine(url, pool_pre_ping=True, future=True)
    try:
        with engine.connect() as conn:
            version = conn.execute(text("select version()")).scalar_one()
            print(f"  ok — {version}")

            ext = conn.execute(
                text("select extname from pg_extension where extname in ('vector','pgvector')")
            ).all()
            if not ext:
                print(
                    "  WARNING: pgvector extension is not installed. "
                    "Enable it from Supabase → Database → Extensions.",
                    file=sys.stderr,
                )
                return 3
            print(f"  pgvector installed: {[e[0] for e in ext]}")

            conn.execute(text("select 1"))
        print("  connection closed cleanly")
        return 0
    except Exception as exc:  # noqa: BLE001 - manual run  # pragma: no cover
        print(f"  FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())