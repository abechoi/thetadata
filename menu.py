#!/usr/bin/env python3
"""
ThetaData Interactive Menu
Navigate all features without memorizing commands
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent


def clear_screen():
    """Clear the terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')


def print_header(title: str):
    """Print a formatted header."""
    clear_screen()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print()


def run_command(cmd: list, wait: bool = True):
    """Run a command and optionally wait for user."""
    try:
        subprocess.run(cmd, cwd=ROOT)
        if wait:
            input("\nPress Enter to continue...")
    except KeyboardInterrupt:
        if wait:
            input("\n\nPress Enter to continue...")
    except Exception as e:
        print(f"\nError: {e}")
        if wait:
            input("\nPress Enter to continue...")


def get_input(prompt: str, default: str = None) -> str:
    """Get user input with optional default."""
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()


def get_years_input() -> str:
    """Get years with smart defaults (current year and previous year)."""
    current_year = datetime.now().year
    default_years = f"{current_year-1},{current_year}"
    years = get_input(f"Years (comma-separated)", default_years)
    return years


def queue_menu():
    """Queue management menu."""
    while True:
        print_header("Queue Management")
        print("1. Add symbol to queue")
        print("2. Remove symbol from queue")
        print("3. View queue")
        print("4. Queue status")
        print("5. Pause queue")
        print("6. Resume queue")
        print("7. Clear queue")
        print("8. Back to main menu")
        print()

        choice = get_input("Select option", "3")

        if choice == "1":
            print()
            symbol = get_input("Symbol (e.g., AAPL)").upper()
            if not symbol:
                print("Symbol required")
                input("\nPress Enter to continue...")
                continue

            years = get_years_input()
            priority = get_input("Priority (1=high, 2=normal)", "1")

            run_command([
                "python3", "queue_manager.py", "add", symbol,
                "--years", years, "--priority", priority
            ])

        elif choice == "2":
            print()
            symbol = get_input("Symbol to remove").upper()
            if symbol:
                run_command(["python3", "queue_manager.py", "remove", symbol])

        elif choice == "3":
            run_command(["python3", "queue_manager.py", "list"])

        elif choice == "4":
            run_command(["python3", "queue_manager.py", "status"])

        elif choice == "5":
            run_command(["python3", "queue_manager.py", "pause"])

        elif choice == "6":
            run_command(["python3", "queue_manager.py", "resume"])

        elif choice == "7":
            print()
            confirm = get_input("Clear entire queue? (yes/no)", "no")
            if confirm.lower() in ['yes', 'y']:
                run_command(["python3", "queue_manager.py", "clear"])

        elif choice == "8":
            break


def service_menu():
    """Service control menu."""
    while True:
        print_header("Service Control")
        print("1. Start services (Terminal + Worker + Watchdog)")
        print("2. Stop services")
        print("3. Check status")
        print("4. Restart services")
        print("5. View worker logs")
        print("6. View terminal logs")
        print("7. View watchdog logs")
        print("8. Back to main menu")
        print()

        choice = get_input("Select option", "3")

        if choice == "1":
            run_command(["./start.sh"])

        elif choice == "2":
            run_command(["./start.sh", "--stop"])

        elif choice == "3":
            run_command(["./start.sh", "--status"])

        elif choice == "4":
            print_header("Restarting Services")
            run_command(["./start.sh", "--stop"], wait=False)
            print("\nWaiting 3 seconds...")
            subprocess.run(["sleep", "3"])
            run_command(["./start.sh"])

        elif choice == "5":
            run_command(["tail", "-100", "logs/priority_backlog_worker.out"])

        elif choice == "6":
            run_command(["tail", "-100", "logs/theta_terminal.out"])

        elif choice == "7":
            if (ROOT / "logs" / "watchdog.log").exists():
                run_command(["tail", "-100", "logs/watchdog.log"])
            else:
                print("No watchdog log yet")
                input("\nPress Enter to continue...")

        elif choice == "8":
            break


def monitoring_menu():
    """Monitoring menu."""
    while True:
        print_header("Monitoring & Dashboards")
        print("1. Live download monitor (real-time progress)")
        print("2. Live monitor (fast refresh - 1 sec)")
        print("3. Live monitor (slow refresh - 5 sec)")
        print("4. Quick status check")
        print("5. Back to main menu")
        print()

        choice = get_input("Select option", "1")

        if choice == "1":
            print_header("Live Download Monitor")
            print("Press Ctrl+C to exit\n")
            run_command(["python3", "monitor.py"], wait=False)
            input("\nPress Enter to continue...")

        elif choice == "2":
            print_header("Live Monitor (Fast)")
            print("Press Ctrl+C to exit\n")
            run_command(["python3", "monitor.py", "--refresh", "1"], wait=False)
            input("\nPress Enter to continue...")

        elif choice == "3":
            print_header("Live Monitor (Slow)")
            print("Press Ctrl+C to exit\n")
            run_command(["python3", "monitor.py", "--refresh", "5"], wait=False)
            input("\nPress Enter to continue...")

        elif choice == "4":
            run_command(["./start.sh", "--status"])

        elif choice == "5":
            break


def inventory_menu():
    """Inventory menu."""
    while True:
        print_header("Inventory & Validation")
        print("1. Summary (all downloads)")
        print("2. List files for specific symbol/year")
        print("3. Find gaps (incomplete downloads)")
        print("4. Validate symbol/year")
        print("5. Export inventory (JSON)")
        print("6. Export inventory (CSV)")
        print("7. Back to main menu")
        print()

        choice = get_input("Select option", "1")

        if choice == "1":
            print_header("Inventory Summary")
            run_command(["python3", "inventory.py", "summary"])

        elif choice == "2":
            print()
            symbol = get_input("Symbol").upper()
            year = get_input("Year", str(datetime.now().year))
            if symbol and year:
                run_command(["python3", "inventory.py", "list", symbol, year])

        elif choice == "3":
            print_header("Finding Gaps")
            run_command(["python3", "inventory.py", "gaps"])

        elif choice == "4":
            print()
            symbol = get_input("Symbol").upper()
            year = get_input("Year", str(datetime.now().year))
            if symbol and year:
                run_command(["python3", "inventory.py", "validate", symbol, year])

        elif choice == "5":
            run_command(["python3", "inventory.py", "export", "--format", "json"])

        elif choice == "6":
            run_command(["python3", "inventory.py", "export", "--format", "csv"])

        elif choice == "7":
            break


def quick_add_menu():
    """Quick add symbols to queue."""
    print_header("Quick Add to Queue")
    print("Add multiple symbols quickly")
    print("Leave symbol blank to finish")
    print()

    years = get_years_input()
    priority = get_input("Priority for all (1=high, 2=normal)", "1")
    print()

    symbols = []
    while True:
        symbol = get_input("Symbol (or blank to finish)").upper()
        if not symbol:
            break
        symbols.append(symbol)

    if symbols:
        print(f"\nAdding {len(symbols)} symbols to queue...")
        for symbol in symbols:
            subprocess.run([
                "python3", "queue_manager.py", "add", symbol,
                "--years", years, "--priority", priority
            ], cwd=ROOT)
            print(f"  ✓ {symbol}")

        print(f"\n✓ Added {len(symbols)} symbols")
        input("\nPress Enter to continue...")


def main_menu():
    """Main menu."""
    while True:
        print_header("ThetaData Control Panel")
        print("1. Queue Management")
        print("2. Service Control (start/stop/status)")
        print("3. Monitoring & Dashboards")
        print("4. Inventory & Validation")
        print("5. Quick Add (add multiple symbols)")
        print("6. Exit")
        print()

        choice = get_input("Select option", "1")

        if choice == "1":
            queue_menu()
        elif choice == "2":
            service_menu()
        elif choice == "3":
            monitoring_menu()
        elif choice == "4":
            inventory_menu()
        elif choice == "5":
            quick_add_menu()
        elif choice == "6":
            print_header("Goodbye!")
            print("ThetaData services are still running in the background.")
            print("Use './start.sh --stop' to stop them.\n")
            sys.exit(0)


if __name__ == '__main__':
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
