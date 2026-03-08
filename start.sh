#!/bin/bash
#
# ThetaData Quick Start Script
# Starts ThetaData Terminal + Priority Backlog Worker
#
# Usage:
#   ./start.sh              # Start everything
#   ./start.sh --status     # Check status only
#   ./start.sh --stop       # Stop everything
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Print with color
print_green() { echo -e "${GREEN}$1${NC}"; }
print_yellow() { echo -e "${YELLOW}$1${NC}"; }
print_red() { echo -e "${RED}$1${NC}"; }

# Check status
check_status() {
    print_yellow "\n📊 Checking ThetaData Status...\n"

    # Check terminal (looks for java processes with thetadata or ThetaTerminal)
    if ps -Ao pid,command | grep -E '[j]ava .*(ThetaTerminal|thetadata)' > /dev/null 2>&1; then
        print_green "✓ ThetaData Terminal: Running"
    else
        print_red "✗ ThetaData Terminal: Not running"
    fi

    # Check worker
    if ps -Ao pid,command | grep -E '[Pp]ython(3)? .*priority_backlog_worker\.py' > /dev/null 2>&1; then
        print_green "✓ Priority Worker: Running"
    else
        print_red "✗ Priority Worker: Not running"
    fi

    # Check watchdog
    if ps -Ao pid,command | grep -E '[Pp]ython(3)? .*watchdog\.py.*--daemon' > /dev/null 2>&1; then
        print_green "✓ Watchdog: Running"
    else
        print_red "✗ Watchdog: Not running"
    fi

    # Check API
    if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:25503/v3/stock/list/symbols?format=csv" | grep -q "200\|472"; then
        print_green "✓ API: Reachable (http://127.0.0.1:25503)"
    else
        print_red "✗ API: Not reachable"
    fi

    # Show queue status
    print_yellow "\n📋 Queue Status:"
    python3 queue_manager.py status

    echo ""
}

# Stop services
stop_services() {
    print_yellow "\n🛑 Stopping ThetaData Services...\n"

    # Stop watchdog first (so it doesn't auto-restart while we're stopping)
    watchdog_pids=$(ps -Ao pid,command | grep -E '[Pp]ython.*watchdog\.py.*--daemon' | awk '{print $1}')
    if [ ! -z "$watchdog_pids" ]; then
        print_yellow "Stopping watchdog (PIDs: $watchdog_pids)..."
        echo "$watchdog_pids" | xargs kill -TERM 2>/dev/null || true
        sleep 1
        print_green "✓ Watchdog stopped"
    fi

    # Stop worker
    worker_pids=$(ps -Ao pid,command | grep -E '[Pp]ython.*priority_backlog_worker\.py' | awk '{print $1}')
    if [ ! -z "$worker_pids" ]; then
        print_yellow "Stopping worker (PIDs: $worker_pids)..."
        echo "$worker_pids" | xargs kill -TERM 2>/dev/null || true

        # Wait up to 5 seconds for graceful shutdown
        for i in {1..5}; do
            sleep 1
            worker_pids=$(ps -Ao pid,command | grep -E '[Pp]ython.*priority_backlog_worker\.py' | awk '{print $1}')
            [ -z "$worker_pids" ] && break
        done

        # Force kill if still running
        if [ ! -z "$worker_pids" ]; then
            print_yellow "Force killing worker..."
            echo "$worker_pids" | xargs kill -9 2>/dev/null || true
            sleep 1
        fi
        print_green "✓ Worker stopped"
    else
        print_yellow "Worker not running"
    fi

    # Stop terminal using proper HTTP endpoint
    if curl -s -f "http://127.0.0.1:25503/v3/terminal/shutdown" > /dev/null 2>&1; then
        print_yellow "Stopping terminal via HTTP shutdown..."

        # Wait up to 10 seconds for terminal to shut down
        for i in {1..10}; do
            sleep 1
            if ! ps -Ao pid,command | grep -E '[j]ava .*(ThetaTerminal|thetadata)' > /dev/null 2>&1; then
                break
            fi
        done

        # Check if terminal actually stopped
        if ps -Ao pid,command | grep -E '[j]ava .*(ThetaTerminal|thetadata)' > /dev/null 2>&1; then
            print_yellow "Terminal still running, forcing shutdown..."
            if [ -f "./scripts/kill_thetadata.sh" ]; then
                ./scripts/kill_thetadata.sh --confirm KILL_THETADATA 2>&1 | grep -v "^Refusing"
                sleep 2
            fi
        fi

        print_green "✓ Terminal stopped"
    else
        # Fallback: use kill script if HTTP doesn't work
        print_yellow "HTTP shutdown not responding..."
        if [ -f "./scripts/kill_thetadata.sh" ]; then
            print_yellow "Using kill script..."
            ./scripts/kill_thetadata.sh --confirm KILL_THETADATA 2>&1 | grep -v "^Refusing"
            sleep 2
        fi
    fi

    # Final verification - ensure everything is stopped
    remaining_workers=$(ps -Ao pid,command | grep -E '[Pp]ython.*priority_backlog_worker\.py' | wc -l | tr -d ' ')
    remaining_terminals=$(ps -Ao pid,command | grep -E '[j]ava .*(ThetaTerminal|thetadata)' | wc -l | tr -d ' ')

    if [ "$remaining_workers" -ne 0 ] || [ "$remaining_terminals" -ne 0 ]; then
        print_yellow "⚠ Some processes still running (Workers: $remaining_workers, Terminals: $remaining_terminals)"
        print_yellow "Run './start.sh --stop' again if needed"
    fi

    # Final cleanup - remove PID files
    rm -f logs/priority_backlog_worker.pid 2>/dev/null || true
    rm -f logs/theta_terminal.pid 2>/dev/null || true

    print_green "\n✓ Stop command completed"
}

# Start services
start_services() {
    print_yellow "\n🚀 Starting ThetaData Services...\n"

    # Check if already running
    term_running=$(ps -Ao pid,command | grep -E '[j]ava .*(ThetaTerminal|thetadata)' > /dev/null 2>&1 && echo 1 || echo 0)
    worker_running=$(ps -Ao pid,command | grep -E '[Pp]ython(3)? .*priority_backlog_worker\.py' > /dev/null 2>&1 && echo 1 || echo 0)

    if [ "$term_running" -eq 1 ] && [ "$worker_running" -eq 1 ]; then
        print_yellow "⚠ Services already running. Use --stop to stop them first."
        check_status
        exit 0
    fi

    # Start terminal and worker
    if [ -f "./scripts/start_thetadata_singleton.sh" ]; then
        ./scripts/start_thetadata_singleton.sh
        print_green "✓ Services started"
    else
        print_red "✗ Start script not found"
        exit 1
    fi

    # Wait a moment for services to initialize
    sleep 2

    # Start watchdog in daemon mode
    mkdir -p logs
    nohup python3 watchdog.py --daemon > logs/watchdog.log 2>&1 &
    print_green "✓ Watchdog started (auto-restart if stuck)"

    # Show status
    check_status

    print_green "\n✅ ThetaData is ready!"
    print_yellow "\n💡 Quick access:"
    echo "   python3 menu.py                    # Interactive menu (easiest!)"
    echo ""
    print_yellow "   Or use commands directly:"
    echo "   python3 monitor.py                 # Live download dashboard"
    echo "   python3 queue_manager.py list      # View download queue"
    echo "   python3 inventory.py summary       # View downloaded data"
    echo "   tail -f logs/watchdog.log          # View watchdog logs"
    echo "   ./start.sh --status                # Check status"
    echo "   ./start.sh --stop                  # Stop services"
    echo ""
}

# Main
case "${1:-}" in
    --status)
        check_status
        ;;
    --stop)
        stop_services
        ;;
    --help|-h)
        echo "Usage: $0 [--status|--stop|--help]"
        echo ""
        echo "Options:"
        echo "  (none)     Start ThetaData Terminal + Worker"
        echo "  --status   Check status of services"
        echo "  --stop     Stop all services"
        echo "  --help     Show this help message"
        echo ""
        ;;
    *)
        start_services
        ;;
esac
