from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.workers.collector import run_collection_once


KST = ZoneInfo("Asia/Seoul")
DEFAULT_RUN_HOURS = [9, 15, 21]


def next_run_time(now: datetime | None = None, run_hours: list[int] | None = None) -> datetime:
    now = now or datetime.now(KST)
    run_hours = run_hours or DEFAULT_RUN_HOURS
    today_candidates = [now.replace(hour=hour, minute=0, second=0, microsecond=0) for hour in run_hours]
    for candidate in today_candidates:
        if candidate > now:
            return candidate
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=run_hours[0], minute=0, second=0, microsecond=0)


def run_once(trigger: str = "manual"):
    init_db()
    settings = get_settings()
    with SessionLocal() as session:
        return run_collection_once(session, settings, trigger=trigger)


def run_forever() -> None:
    init_db()
    while True:
        target = next_run_time()
        sleep_seconds = max(1, (target - datetime.now(KST)).total_seconds())
        print(f"next collection run: {target.isoformat()} KST", flush=True)
        time.sleep(sleep_seconds)
        run_once(trigger="scheduled")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one collection cycle and exit.")
    args = parser.parse_args()
    if args.once:
        run = run_once(trigger="manual")
        print({"id": run.id, "status": run.status, "message": run.message})
        return
    run_forever()


if __name__ == "__main__":
    main()
