#!/usr/bin/env python3
"""
Queue Manager for ThetaData Downloads

Manage a persistent queue of symbols to download without editing code.

Usage:
    python queue_manager.py add SYMBOL [--years 2024,2025] [--priority 1]
    python queue_manager.py remove SYMBOL
    python queue_manager.py list
    python queue_manager.py clear
    python queue_manager.py status
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Default queue file location
QUEUE_FILE = Path(__file__).parent / "queue.json"

# Default years if not specified
DEFAULT_YEARS = [2021, 2022, 2023, 2024, 2025]


def load_queue() -> Dict[str, Any]:
    """Load queue from file, creating default if it doesn't exist."""
    if not QUEUE_FILE.exists():
        return {
            "symbols": [],
            "active": True,
            "auto_reload": True
        }

    try:
        with open(QUEUE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading queue: {e}", file=sys.stderr)
        return {"symbols": [], "active": True, "auto_reload": True}


def save_queue(queue: Dict[str, Any]) -> None:
    """Save queue to file."""
    try:
        with open(QUEUE_FILE, 'w') as f:
            json.dump(queue, f, indent=2, sort_keys=True)
        print(f"✓ Queue saved to {QUEUE_FILE}")
    except IOError as e:
        print(f"✗ Error saving queue: {e}", file=sys.stderr)
        sys.exit(1)


def add_symbol(symbol: str, years: List[int], priority: int = 1) -> None:
    """Add a symbol to the queue."""
    queue = load_queue()

    # Check if symbol already exists
    existing = next((s for s in queue["symbols"] if s["symbol"] == symbol), None)

    if existing:
        # Update existing entry
        existing["years"] = sorted(list(set(existing["years"] + years)))
        existing["priority"] = priority
        print(f"✓ Updated {symbol}: years={existing['years']}, priority={priority}")
    else:
        # Add new entry
        queue["symbols"].append({
            "symbol": symbol.upper(),
            "years": sorted(years),
            "priority": priority
        })
        print(f"✓ Added {symbol}: years={years}, priority={priority}")

    # Sort by priority (lower number = higher priority)
    queue["symbols"].sort(key=lambda x: (x["priority"], x["symbol"]))

    save_queue(queue)


def remove_symbol(symbol: str) -> None:
    """Remove a symbol from the queue."""
    queue = load_queue()

    original_count = len(queue["symbols"])
    queue["symbols"] = [s for s in queue["symbols"] if s["symbol"] != symbol.upper()]

    if len(queue["symbols"]) < original_count:
        print(f"✓ Removed {symbol}")
        save_queue(queue)
    else:
        print(f"✗ Symbol {symbol} not found in queue", file=sys.stderr)
        sys.exit(1)


def list_queue() -> None:
    """List all symbols in the queue."""
    queue = load_queue()

    if not queue["symbols"]:
        print("Queue is empty")
        return

    print(f"\n{'Symbol':<10} {'Years':<30} {'Priority':<10}")
    print("=" * 60)

    for entry in queue["symbols"]:
        years_str = ",".join(map(str, entry["years"]))
        print(f"{entry['symbol']:<10} {years_str:<30} {entry['priority']:<10}")

    print(f"\nTotal: {len(queue['symbols'])} symbols")
    print(f"Status: {'Active' if queue.get('active', True) else 'Paused'}")
    print(f"Auto-reload: {'Enabled' if queue.get('auto_reload', True) else 'Disabled'}")


def clear_queue() -> None:
    """Clear all symbols from the queue."""
    queue = load_queue()
    count = len(queue["symbols"])
    queue["symbols"] = []
    save_queue(queue)
    print(f"✓ Cleared {count} symbols from queue")


def show_status() -> None:
    """Show queue status and statistics."""
    queue = load_queue()

    total_symbols = len(queue["symbols"])
    total_years = sum(len(s["years"]) for s in queue["symbols"])

    print(f"\nQueue Status:")
    print(f"  File: {QUEUE_FILE}")
    print(f"  Active: {'Yes' if queue.get('active', True) else 'No'}")
    print(f"  Auto-reload: {'Yes' if queue.get('auto_reload', True) else 'No'}")
    print(f"  Symbols: {total_symbols}")
    print(f"  Symbol-Year pairs: {total_years}")

    if queue["symbols"]:
        priorities = {}
        for s in queue["symbols"]:
            p = s["priority"]
            priorities[p] = priorities.get(p, 0) + 1

        print(f"\nBy Priority:")
        for p in sorted(priorities.keys()):
            print(f"  Priority {p}: {priorities[p]} symbols")


def toggle_active(active: bool) -> None:
    """Enable or disable the queue."""
    queue = load_queue()
    queue["active"] = active
    save_queue(queue)
    print(f"✓ Queue {'activated' if active else 'paused'}")


def get_next_symbols() -> List[Dict[str, Any]]:
    """Get symbols from queue for worker consumption (used by workers)."""
    queue = load_queue()

    if not queue.get("active", True):
        return []

    return queue["symbols"]


def main():
    parser = argparse.ArgumentParser(description="Manage ThetaData download queue")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add symbol to queue")
    add_parser.add_argument("symbol", help="Symbol to add (e.g., AAPL)")
    add_parser.add_argument("--years", help="Comma-separated years (e.g., 2024,2025)")
    add_parser.add_argument("--priority", type=int, default=1, help="Priority (1=highest)")

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove symbol from queue")
    remove_parser.add_argument("symbol", help="Symbol to remove")

    # List command
    subparsers.add_parser("list", help="List all symbols in queue")

    # Clear command
    subparsers.add_parser("clear", help="Clear all symbols from queue")

    # Status command
    subparsers.add_parser("status", help="Show queue status")

    # Pause/Resume commands
    subparsers.add_parser("pause", help="Pause queue processing")
    subparsers.add_parser("resume", help="Resume queue processing")

    args = parser.parse_args()

    if args.command == "add":
        if args.years:
            years = [int(y.strip()) for y in args.years.split(",")]
        else:
            years = DEFAULT_YEARS
        add_symbol(args.symbol, years, args.priority)

    elif args.command == "remove":
        remove_symbol(args.symbol)

    elif args.command == "list":
        list_queue()

    elif args.command == "clear":
        clear_queue()

    elif args.command == "status":
        show_status()

    elif args.command == "pause":
        toggle_active(False)

    elif args.command == "resume":
        toggle_active(True)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
