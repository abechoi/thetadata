#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/Users/abe/Projects/thetadata')
DATA = ROOT / 'data'
LOGS = ROOT / 'logs'
LOGS.mkdir(exist_ok=True)
PID_FILE = LOGS / 'hourly_backlog_worker.pid'
STATUS_FILE = LOGS / 'hourly_backlog_status.json'

sys.path.insert(0, str(ROOT))
import downloader as dl  # noqa: E402

REQUIRED = [
    'options_eod.csv',
    'options_open_interest.csv',
    'options_trades.csv',
    'stock_eod.csv',
    'stock_trades.csv',
    'iv_hourly.csv',
    'iv_spikes.csv',
]


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        cmd = Path(f'/proc/{pid}/cmdline').read_text() if Path('/proc').exists() else ''
    except Exception:
        cmd = ''
    if not cmd:
        try:
            out = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True).strip()
            cmd = out
        except Exception:
            return False
    return 'hourly_backlog_worker.py' in cmd


def write_status(**kwargs):
    state = {
        'ts': int(time.time()),
        **kwargs,
    }
    STATUS_FILE.write_text(json.dumps(state, indent=2))


def ensure_terminal():
    if dl.check_terminal():
        return 'running'
    subprocess.Popen(
        ['java', '-jar', str(ROOT / 'ThetaTerminalv3.jar')],
        cwd=str(ROOT),
        stdout=open(LOGS / 'theta_terminal.out', 'a'),
        stderr=open(LOGS / 'theta_terminal.err', 'a'),
        start_new_session=True,
    )
    for _ in range(20):
        time.sleep(3)
        if dl.check_terminal():
            return 'started'
    return 'failed'


def file_ready(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def year_complete(symbol: str, year: int) -> bool:
    d = DATA / symbol / str(year)
    return all(file_ready(d / f) for f in REQUIRED)


def list_exp(symbol: str, year: int) -> list[str]:
    all_exps = dl.list_expirations(symbol)
    return dl.filter_expirations_by_year(all_exps, year)


def run_year(symbol: str, year: int):
    d = DATA / symbol / str(year)
    d.mkdir(parents=True, exist_ok=True)

    exps = list_exp(symbol, year)
    if not exps:
        write_status(state='error', active_task=f'{symbol} {year}', error='no expirations found')
        return

    tasks = [
        ('options_eod.csv', lambda: dl.download_options_eod(symbol, year, DATA, exps, force_fresh=False)),
        ('options_open_interest.csv', lambda: dl.download_options_open_interest(symbol, year, DATA, exps, force_fresh=False)),
        ('options_trades.csv', lambda: dl.download_options_trades(symbol, year, DATA, exps, force_fresh=False)),
        ('stock_eod.csv', lambda: dl.download_stock_eod(symbol, year, DATA, force_fresh=False)),
        ('stock_trades.csv', lambda: dl.download_stock_trades(symbol, year, DATA, force_fresh=False)),
        ('iv_hourly.csv', lambda: dl.download_iv_spikes(symbol, year, DATA, exps, force_fresh=False)),
    ]

    for fname, fn in tasks:
        path = d / fname
        if file_ready(path):
            continue
        write_status(state='running', active_task=f'{symbol} {year} {fname}', symbol=symbol, year=year)
        fn()


def build_backlog() -> list[tuple[str, int]]:
    current_year = time.localtime().tm_year
    plan = []
    plan += [('AAPL', y) for y in [2024, 2023, 2022, 2021]]
    plan += [('NVDA', y) for y in range(2021, current_year + 1)]
    return plan


def cleanup(*_):
    if PID_FILE.exists():
        PID_FILE.unlink()


def main():
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if is_running(pid):
                write_status(state='already_running', pid=pid)
                return
            else:
                PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    PID_FILE.write_text(str(os.getpid()))
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    term = ensure_terminal()
    if term == 'failed':
        write_status(state='error', error='Theta terminal unavailable')
        cleanup()
        return

    write_status(state='running', active_task='planning', terminal=term)

    for symbol, year in build_backlog():
        if year_complete(symbol, year):
            continue
        run_year(symbol, year)

    write_status(state='complete', active_task='all requested years complete')
    cleanup()


if __name__ == '__main__':
    main()
