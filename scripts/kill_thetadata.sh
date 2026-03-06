#!/usr/bin/env bash
set -euo pipefail

# Kill-switch for ThetaData terminal Java processes.
# Targets only Java processes whose command line contains "ThetaTerminalv3.jar".
#
# Usage:
#   ./scripts/kill_thetadata.sh --dry-run
#   ./scripts/kill_thetadata.sh --confirm KILL_THETADATA
#
# Exit codes:
#   0 = success (or nothing to kill)
#   1 = invalid usage / confirmation missing
#   2 = processes still alive after escalation

CONFIRM_VALUE=""
DRY_RUN=false
TIMEOUT_SEC=8

list_pids() {
  ps -Ao pid,command | grep -E '[j]ava .*ThetaTerminalv3\.jar' | awk '{print $1}' || true
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --confirm)
      CONFIRM_VALUE="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SEC="${2:-8}"
      shift 2
      ;;
    -h|--help)
      sed -n '1,40p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

if [[ "$DRY_RUN" == false && "$CONFIRM_VALUE" != "KILL_THETADATA" ]]; then
  echo "Refusing to kill: pass --confirm KILL_THETADATA (or use --dry-run)." >&2
  exit 1
fi

PIDS=( $(list_pids) )

if [[ ${#PIDS[@]} -eq 0 ]]; then
  echo "No ThetaData jar processes found."
  exit 0
fi

echo "Found ${#PIDS[@]} ThetaData jar process(es):"
ps -Ao pid,ppid,etime,command | awk 'NR==1{print;next} /java/ && /ThetaTerminalv3\.jar/'

if [[ "$DRY_RUN" == true ]]; then
  echo "Dry-run only. No processes were killed."
  exit 0
fi

echo "Sending SIGTERM..."
kill -TERM "${PIDS[@]}" 2>/dev/null || true

end=$((SECONDS + TIMEOUT_SEC))
while (( SECONDS < end )); do
  sleep 1
  REMAINING=( $(list_pids) )
  if [[ ${#REMAINING[@]} -eq 0 ]]; then
    echo "All ThetaData jar processes stopped cleanly."
    break
  fi
done

REMAINING=( $(list_pids) )
if [[ ${#REMAINING[@]} -gt 0 ]]; then
  echo "Escalating to SIGKILL for remaining PID(s): ${REMAINING[*]}"
  kill -KILL "${REMAINING[@]}" 2>/dev/null || true
  sleep 1
fi

FINAL=( $(list_pids) )
if [[ ${#FINAL[@]} -gt 0 ]]; then
  echo "FAIL: ThetaData jar process(es) still alive: ${FINAL[*]}" >&2
  exit 2
fi

echo "Confirmed: no ThetaData jar processes remain."
