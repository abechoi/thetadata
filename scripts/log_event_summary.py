#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize structured ThetaData JSON events from worker logs")
    p.add_argument("--log", default="/Users/abe/Projects/thetadata/logs/priority_backlog_worker.out")
    p.add_argument("--minutes", type=int, default=10)
    p.add_argument("--top", type=int, default=5)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    log_path = Path(args.log)
    if not log_path.exists():
        print(f"log_missing path={log_path}")
        return 1

    cutoff = time.time() - args.minutes * 60

    events = Counter()
    status = Counter()
    endpoints = Counter()
    total_json = 0

    with log_path.open("r", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("{") or '"event"' not in line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            ts = obj.get("ts", "")
            # ts format: 2026-03-06T03:05:59Z
            try:
                event_epoch = time.mktime(time.strptime(ts.replace("Z", ""), "%Y-%m-%dT%H:%M:%S"))
            except Exception:
                event_epoch = None

            if event_epoch is not None and event_epoch < cutoff:
                continue

            total_json += 1
            ev = obj.get("event", "unknown")
            events[ev] += 1
            if "status" in obj:
                status[str(obj["status"])] += 1
            if "url" in obj:
                endpoints[str(obj["url"])] += 1

    transient = sum(events[e] for e in ["http_transient", "request_exception", "http_retry"])
    permanent = sum(events[e] for e in ["http_permanent", "http_plan_or_forbidden"])
    give_up = events.get("give_up", 0)

    print(f"window_minutes={args.minutes} total_json_events={total_json}")
    print(f"transient={transient} permanent={permanent} give_up={give_up}")

    print("events_top=")
    for k, v in events.most_common(args.top):
        print(f"  {k}: {v}")

    if status:
        print("status_top=")
        for k, v in status.most_common(args.top):
            print(f"  {k}: {v}")

    if endpoints:
        print("endpoints_top=")
        for k, v in endpoints.most_common(args.top):
            print(f"  {k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
