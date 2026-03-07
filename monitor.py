#!/usr/bin/env python3
"""
ThetaData Download Monitor - Simple Version

Real-time dashboard showing current download progress, ETA, and queue.

Usage:
    python3 monitor.py
    python3 monitor.py --refresh 1  # Update every 1 second (default: 2)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# Project paths
ROOT = Path(__file__).parent
STATUS_FILE = ROOT / 'logs' / 'priority_backlog_status.json'
QUEUE_FILE = ROOT / 'queue.json'
DATA_DIR = ROOT / 'data'


def clear_screen():
    """Clear the terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')


def human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def format_time(seconds: float) -> str:
    """Format seconds to human-readable time."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}m {int(seconds%60)}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


class ProgressTracker:
    """Track download progress over time."""
    def __init__(self):
        self.history: Dict[str, List] = {}
        self.max_history = 10

    def update(self, file_path: str, size: int):
        """Update size for a file."""
        now = time.time()
        if file_path not in self.history:
            self.history[file_path] = []
        self.history[file_path].append((now, size))
        if len(self.history[file_path]) > self.max_history:
            self.history[file_path] = self.history[file_path][-self.max_history:]

    def get_speed(self, file_path: str) -> Optional[float]:
        """Calculate bytes per second."""
        if file_path not in self.history or len(self.history[file_path]) < 2:
            return None
        oldest = self.history[file_path][0]
        newest = self.history[file_path][-1]
        time_diff = newest[0] - oldest[0]
        size_diff = newest[1] - oldest[1]
        if time_diff > 0 and size_diff > 0:
            return size_diff / time_diff
        return None

    def get_eta(self, file_path: str, current_size: int, expected_size: int) -> Optional[float]:
        """Calculate ETA in seconds."""
        speed = self.get_speed(file_path)
        if speed and speed > 100 and expected_size > current_size:
            remaining = expected_size - current_size
            return min(remaining / speed, 86400)
        return None


def load_status() -> Optional[Dict]:
    """Load current worker status."""
    if not STATUS_FILE.exists():
        return None
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except:
        return None


def load_queue() -> Dict:
    """Load download queue."""
    if not QUEUE_FILE.exists():
        return {'symbols': [], 'active': False}
    try:
        with open(QUEUE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'symbols': [], 'active': False}


def get_file_size(file_path: Path) -> int:
    """Get current file size."""
    if file_path.exists():
        return file_path.stat().st_size
    return 0


def estimate_file_size(symbol: str, year: int, filename: str) -> Optional[int]:
    """Estimate expected file size based on other years."""
    estimates = []
    symbol_dir = DATA_DIR / symbol
    if symbol_dir.exists():
        for year_dir in symbol_dir.iterdir():
            if year_dir.is_dir() and year_dir.name != str(year):
                file_path = year_dir / filename
                if file_path.exists():
                    size = file_path.stat().st_size
                    if size > 0:
                        estimates.append(size)
    if estimates:
        return int(sum(estimates) / len(estimates))
    # Fallback: check other symbols
    for other_dir in DATA_DIR.iterdir():
        if other_dir.is_dir() and other_dir.name != symbol:
            for year_dir in other_dir.iterdir():
                if year_dir.is_dir():
                    file_path = year_dir / filename
                    if file_path.exists() and file_path.stat().st_size > 0:
                        estimates.append(file_path.stat().st_size)
            if estimates:
                return int(sum(estimates) / len(estimates))
    return None


def build_queue_list(queue_data: Dict) -> List[tuple]:
    """Build list of (symbol, year, priority) from queue."""
    queue_list = []
    for entry in queue_data.get('symbols', []):
        symbol = entry['symbol']
        years = entry.get('years', [])
        priority = entry.get('priority', 1)
        for year in years:
            queue_list.append((symbol, year, priority))
    queue_list.sort(key=lambda x: (x[2], x[0], x[1]))
    return queue_list


def render_dashboard(status: Optional[Dict], queue_data: Dict, tracker: ProgressTracker):
    """Render the monitoring dashboard."""
    clear_screen()

    # Header
    print("=" * 80)
    print("  ThetaData Download Monitor")
    print("=" * 80)
    print()

    # Current download
    print("Current Download:")
    print("-" * 80)

    if status and status.get('state') == 'running':
        symbol = status.get('symbol', 'Unknown')
        year = status.get('year', '????')
        active_task = status.get('active_task', 'Unknown')
        active_file = status.get('active_file', '')

        if ' ' in active_task:
            filename = active_task.split(' ')[-1]
        else:
            filename = 'unknown.csv'

        print(f"● DOWNLOADING  {symbol} / {year} / {filename}")
        print()

        if active_file:
            file_path = Path(active_file)
            current_size = get_file_size(file_path)
            estimated_size = estimate_file_size(symbol, year, filename)

            tracker.update(str(file_path), current_size)
            speed = tracker.get_speed(str(file_path))

            if estimated_size and estimated_size > 0 and current_size <= estimated_size:
                progress_pct = (current_size / estimated_size) * 100
                eta = tracker.get_eta(str(file_path), current_size, estimated_size)

                print(f"Size:     {human_size(current_size)} / {human_size(estimated_size)}")
                print(f"Progress: {progress_pct:.1f}%")

                # Progress bar
                bar_width = 60
                filled = int(bar_width * progress_pct / 100)
                bar = '█' * filled + '░' * (bar_width - filled)
                print(f"[{bar}]")
                print()

                if speed and speed > 0:
                    print(f"Speed:    {human_size(speed)}/s")
                else:
                    print(f"Speed:    Calculating...")

                if eta and eta > 0:
                    print(f"ETA:      {format_time(eta)}")
                else:
                    print(f"ETA:      Calculating...")
            else:
                print(f"Size:     {human_size(current_size)} (estimating total...)")
                if speed and speed > 0:
                    print(f"Speed:    {human_size(speed)}/s")
                else:
                    print(f"Speed:    Calculating...")
                print(f"Progress: Monitoring...")

        ts = status.get('ts', 0)
        if ts:
            last_update = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
            print(f"Last update: {last_update}")

    elif status and status.get('state') == 'complete':
        print("✓ ALL DOWNLOADS COMPLETE")
    elif status and status.get('state') == 'error':
        error = status.get('error', 'Unknown error')
        print(f"✗ ERROR: {error}")
    elif status and status.get('state') == 'paused':
        print("⏸ PAUSED")
    else:
        print("⚠ Worker not running")

    print()

    # Queue
    print("Download Queue (Pending):")
    print("-" * 80)

    queue_list = build_queue_list(queue_data)
    incomplete_items = []
    completed_count = 0

    required_files = [
        'options_eod.csv', 'options_open_interest.csv', 'options_trades.csv',
        'stock_eod.csv', 'stock_trades.csv', 'iv_hourly.csv', 'iv_spikes.csv'
    ]

    for symbol, year, priority in queue_list:
        symbol_dir = DATA_DIR / symbol / str(year)
        complete = all((symbol_dir / f).exists() and (symbol_dir / f).stat().st_size > 0
                      for f in required_files)
        is_current = (status and status.get('symbol') == symbol and
                     status.get('year') == year and status.get('state') == 'running')

        if complete:
            completed_count += 1
        else:
            incomplete_items.append((symbol, year, priority, is_current))

    if not incomplete_items:
        print("✓ All items in queue are complete!")
    else:
        max_display = 20
        for idx, (symbol, year, priority, is_current) in enumerate(incomplete_items):
            if idx >= max_display:
                remaining = len(incomplete_items) - idx
                print(f"  ... and {remaining} more")
                break

            if is_current:
                print(f"  ▶ {symbol}/{year} (Priority {priority}) - Downloading Now")
            else:
                print(f"  ○ {symbol}/{year} (Priority {priority}) - Queued")

    if completed_count > 0:
        print()
        print(f"  ✓ {completed_count} completed items hidden")

    print()

    # Footer
    queue_active = queue_data.get('active', False)
    total_pairs = len(queue_list)
    pending_count = len(incomplete_items)

    print("-" * 80)
    status_text = "Active" if queue_active else "Paused"
    print(f"Status: {status_text} | Pending: {pending_count} | "
          f"Completed: {completed_count}/{total_pairs} | Time: {datetime.now().strftime('%H:%M:%S')}")
    print()
    print("Press Ctrl+C to exit")


def main():
    parser = argparse.ArgumentParser(description="ThetaData Download Monitor")
    parser.add_argument('--refresh', type=int, default=2,
                       help='Refresh interval in seconds (default: 2)')
    args = parser.parse_args()

    tracker = ProgressTracker()

    try:
        while True:
            status = load_status()
            queue_data = load_queue()
            render_dashboard(status, queue_data, tracker)
            time.sleep(args.refresh)
    except KeyboardInterrupt:
        clear_screen()
        print("\nMonitoring stopped.\n")
        sys.exit(0)


if __name__ == '__main__':
    main()
