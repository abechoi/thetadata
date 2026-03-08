#!/usr/bin/env python3
"""
ThetaData Watchdog - Monitors worker health and restarts if stuck

Checks:
1. Worker process is running
2. Status file is being updated (< 10 minutes old)
3. Terminal is responding
4. Auto-restarts if issues detected

Usage:
    python3 watchdog.py           # Run once
    python3 watchdog.py --daemon  # Run continuously (checks every 5 min)
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# Config
ROOT = Path(__file__).parent
STATUS_FILE = ROOT / 'logs' / 'priority_backlog_status.json'
MAX_STATUS_AGE = 600  # 10 minutes
CHECK_INTERVAL = 300  # 5 minutes

def log(msg: str):
    """Print with timestamp."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")

def check_worker_running() -> bool:
    """Check if worker process is running."""
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )
        return 'priority_backlog_worker.py' in result.stdout
    except:
        return False

def check_status_fresh() -> tuple[bool, int]:
    """Check if status file is recent. Returns (is_fresh, age_seconds)."""
    if not STATUS_FILE.exists():
        return False, -1

    try:
        with open(STATUS_FILE) as f:
            status = json.load(f)

        status_ts = status.get('ts', 0)
        current_ts = int(time.time())
        age = current_ts - status_ts

        return age < MAX_STATUS_AGE, age
    except:
        return False, -1

def check_terminal_responding() -> bool:
    """Check if terminal API is responding."""
    try:
        result = subprocess.run(
            ['curl', '-s', '-f', '--max-time', '5',
             'http://127.0.0.1:25503/v3/stock/list/symbols?format=csv'],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False

def restart_services():
    """Restart worker and terminal."""
    log("⚠ Restarting services...")

    try:
        # Stop
        subprocess.run(
            [str(ROOT / 'start.sh'), '--stop'],
            cwd=ROOT,
            timeout=60
        )
        time.sleep(3)

        # Start
        result = subprocess.run(
            [str(ROOT / 'start.sh')],
            cwd=ROOT,
            timeout=120
        )

        if result.returncode == 0:
            log("✓ Services restarted successfully")
            return True
        else:
            log("✗ Service restart failed")
            return False
    except Exception as e:
        log(f"✗ Error restarting services: {e}")
        return False

def check_health() -> bool:
    """
    Perform health check and restart if needed.
    Returns True if healthy or successfully restarted.
    """
    log("Running health check...")

    # Check 1: Worker running
    worker_running = check_worker_running()
    if not worker_running:
        log("✗ Worker not running")
        return restart_services()

    log("✓ Worker process running")

    # Check 2: Status fresh
    status_fresh, age = check_status_fresh()
    if not status_fresh:
        if age < 0:
            log("✗ Status file missing or invalid")
        else:
            log(f"✗ Status file stale ({age} seconds old, max {MAX_STATUS_AGE})")
        log("⚠ Worker appears stuck")
        return restart_services()

    log(f"✓ Status fresh ({age} seconds old)")

    # Check 3: Terminal responding
    terminal_ok = check_terminal_responding()
    if not terminal_ok:
        log("✗ Terminal not responding")
        return restart_services()

    log("✓ Terminal responding")
    log("✓ All health checks passed")
    return True

def main():
    parser = argparse.ArgumentParser(description="ThetaData Watchdog")
    parser.add_argument('--daemon', action='store_true',
                       help='Run continuously (check every 5 minutes)')
    args = parser.parse_args()

    log("ThetaData Watchdog started")

    if args.daemon:
        log(f"Running in daemon mode (checking every {CHECK_INTERVAL/60:.0f} minutes)")

        while True:
            try:
                check_health()
            except KeyboardInterrupt:
                log("Watchdog stopped by user")
                sys.exit(0)
            except Exception as e:
                log(f"✗ Error during health check: {e}")

            log(f"Sleeping for {CHECK_INTERVAL/60:.0f} minutes...\n")
            time.sleep(CHECK_INTERVAL)
    else:
        # Single check
        healthy = check_health()
        sys.exit(0 if healthy else 1)

if __name__ == '__main__':
    main()
