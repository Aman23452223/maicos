"""Standalone worker process entry point.

Run with: `python -m app.workers.scheduler`

Kept as a thin wrapper around `app.queue.worker.main` so existing
operator runbooks (`python -m app.workers.scheduler`) continue to
work. The worker uses Postgres `LISTEN/NOTIFY` + `FOR UPDATE SKIP
LOCKED` and no longer needs Redis.
"""
from app.queue.worker import main

if __name__ == "__main__":
    main()