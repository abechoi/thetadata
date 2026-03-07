#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/abe/Projects/thetadata"
cd "$PROJECT_ROOT"

TERMINAL_CMD='java -jar ThetaTerminalv3.jar'
WORKER_CMD="python3 $PROJECT_ROOT/scripts/priority_backlog_worker.py"

count_terminal() {
  (ps -Ao pid,command | grep -E '[j]ava .*(ThetaTerminal|thetadata)' || true) | wc -l | tr -d ' '
}

count_worker() {
  (ps -Ao pid,command | grep -Ei '[Pp]ython(3)? .*priority_backlog_worker\.py' || true) | wc -l | tr -d ' '
}

list_terminal_pids() {
  ps -Ao pid,command | grep -E '[j]ava .*(ThetaTerminal|thetadata)' | awk '{print $1}' || true
}

list_worker_pids() {
  ps -Ao pid,command | grep -Ei '[Pp]ython(3)? .*priority_backlog_worker\.py' | awk '{print $1}' || true
}

api_probe() {
  python3 - <<'PY'
import urllib.request
import sys
url = 'http://127.0.0.1:25503/v3/stock/list/symbols?format=csv'
try:
    with urllib.request.urlopen(url, timeout=5) as r:
        print(f'API_PROBE: HTTP {getattr(r, "status", "200")}')
except Exception as e:
    print(f'API_PROBE: FAIL {e}')
    sys.exit(1)
PY
}

echo "[thetadata-startup] precheck"
echo "terminal_count=$(count_terminal) worker_count=$(count_worker)"

# Dedupe terminal: keep oldest PID if >1
term_pids=( $(list_terminal_pids || true) )
if [[ ${#term_pids[@]} -gt 1 ]]; then
  keep="${term_pids[0]}"
  echo "[thetadata-startup] duplicate terminals detected: ${term_pids[*]} (keeping $keep)"
  for p in "${term_pids[@]}"; do
    [[ "$p" == "$keep" ]] && continue
    kill -TERM "$p" 2>/dev/null || true
  done
  sleep 1
fi

# Start terminal if missing
if [[ "$(count_terminal)" -eq 0 ]]; then
  echo "[thetadata-startup] starting terminal"
  cd "$PROJECT_ROOT"
  nohup java -jar ThetaTerminalv3.jar >> logs/theta_terminal.out 2>> logs/theta_terminal.err &
  sleep 3
fi

# Dedupe worker: keep oldest PID if >1
worker_pids=( $(list_worker_pids || true) )
if [[ ${#worker_pids[@]} -gt 1 ]]; then
  keep="${worker_pids[0]}"
  echo "[thetadata-startup] duplicate workers detected: ${worker_pids[*]} (keeping $keep)"
  for p in "${worker_pids[@]}"; do
    [[ "$p" == "$keep" ]] && continue
    kill -TERM "$p" 2>/dev/null || true
  done
  sleep 1
fi

# Start worker if missing
if [[ "$(count_worker)" -eq 0 ]]; then
  echo "[thetadata-startup] starting worker"
  cd "$PROJECT_ROOT"
  nohup python3 "$PROJECT_ROOT/scripts/priority_backlog_worker.py" >> logs/priority_backlog_worker.out 2>> logs/priority_backlog_worker.err &
  sleep 3
fi

echo "[thetadata-startup] final check"
term_final="$(count_terminal)"
worker_final="$(count_worker)"
echo "terminal_count=$term_final worker_count=$worker_final"

if api_probe; then
  api_ok=1
else
  api_ok=0
fi

# Accept 1 or 2 terminals (ThetaTerminalv3.jar spawns a child process)
if [[ ("$term_final" -eq 1 || "$term_final" -eq 2) && "$worker_final" -eq 1 && "$api_ok" -eq 1 ]]; then
  echo "RESULT: OK singleton verified"
  exit 0
fi

echo "RESULT: FAIL singleton/API check"
echo "Expected: terminal=1-2, worker=1, api=OK"
echo "Got: terminal=$term_final, worker=$worker_final, api=$([[ "$api_ok" -eq 1 ]] && echo 'OK' || echo 'FAIL')"
exit 2
