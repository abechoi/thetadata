#!/usr/bin/env python3
from __future__ import annotations
import json, os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path('/Users/abe/Projects/thetadata')
DATA = ROOT / 'data'
LOGS = ROOT / 'logs'
LOGS.mkdir(exist_ok=True)
PID_FILE = LOGS / 'priority_backlog_worker.pid'
STATUS_FILE = LOGS / 'priority_backlog_status.json'
QUEUE_FILE = ROOT / 'queue.json'

sys.path.insert(0, str(ROOT))
import downloader as dl

# Fallback symbols if queue.json doesn't exist
FALLBACK_SYMBOLS = ['AAPL','NVDA','NFLX','TSLA','SPY','QQQ','META','MRNA','BNTX']
FALLBACK_YEARS = [2021, 2022, 2023, 2024, 2025]
REQUIRED = [
    'options_eod.csv','options_open_interest.csv','options_trades.csv',
    'stock_eod.csv','stock_trades.csv','iv_hourly.csv','iv_spikes.csv'
]

# Queue reload interval (check for new symbols every N iterations)
RELOAD_INTERVAL = 10
last_queue_load_time = 0
queue_cache = None

def load_queue():
    """Load symbol queue from queue.json, with fallback to hardcoded list."""
    global queue_cache, last_queue_load_time

    # Use cache if recently loaded (within 60 seconds)
    current_time = time.time()
    if queue_cache and (current_time - last_queue_load_time) < 60:
        return queue_cache

    # Try to load from queue.json
    if QUEUE_FILE.exists():
        try:
            with open(QUEUE_FILE, 'r') as f:
                queue_data = json.load(f)

            # Check if queue is active
            if not queue_data.get('active', True):
                write_status(state='paused', message='Queue is paused')
                return {'symbols': [], 'active': False}

            # Extract symbols and years from queue
            symbols_list = []
            for entry in queue_data.get('symbols', []):
                symbol = entry['symbol']
                years = entry.get('years', FALLBACK_YEARS)
                for year in years:
                    symbols_list.append((symbol, year, entry.get('priority', 1)))

            # Sort by priority (lower number = higher priority)
            symbols_list.sort(key=lambda x: (x[2], x[0], x[1]))

            queue_cache = {
                'symbols': [(s, y) for s, y, _ in symbols_list],
                'active': True
            }
            last_queue_load_time = current_time
            return queue_cache

        except (json.JSONDecodeError, IOError) as e:
            write_status(state='warning', message=f'Queue load failed: {e}, using fallback')

    # Fallback to hardcoded symbols
    symbols_list = [(s, y) for s in FALLBACK_SYMBOLS for y in FALLBACK_YEARS]
    queue_cache = {'symbols': symbols_list, 'active': True}
    last_queue_load_time = current_time
    return queue_cache

def is_running(pid:int)->bool:
    try: os.kill(pid,0)
    except OSError: return False
    try: out=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True).strip()
    except Exception: return False
    return 'priority_backlog_worker.py' in out

def write_status(**kwargs):
    STATUS_FILE.write_text(json.dumps({'ts':int(time.time()),**kwargs},indent=2))

def file_ready(p:Path)->bool:
    return p.exists() and p.stat().st_size>0

def next_missing():
    """Find next symbol/year with missing files from queue."""
    queue = load_queue()

    if not queue['active']:
        return None

    for s, y in queue['symbols']:
        d = DATA / s / str(y)
        miss = [f for f in REQUIRED if not file_ready(d / f)]
        if miss:
            return s, y, miss

    return None

def run_year(symbol:str, year:int):
    d=DATA/symbol/str(year); d.mkdir(parents=True,exist_ok=True)
    exps=dl.filter_expirations_by_year(dl.list_expirations(symbol), year)
    if not exps:
      write_status(state='error',active_task=f'{symbol}-{year}',error='no expirations found'); time.sleep(60); return
    tasks=[
      ('options_eod.csv', lambda: dl.download_options_eod(symbol,year,DATA,exps,force_fresh=False)),
      ('options_open_interest.csv', lambda: dl.download_options_open_interest(symbol,year,DATA,exps,force_fresh=False)),
      ('options_trades.csv', lambda: dl.download_options_trades(symbol,year,DATA,exps,force_fresh=False)),
      ('stock_eod.csv', lambda: dl.download_stock_eod(symbol,year,DATA,force_fresh=False)),
      ('stock_trades.csv', lambda: dl.download_stock_trades(symbol,year,DATA,force_fresh=False)),
      ('iv_hourly.csv', lambda: dl.download_iv_spikes(symbol,year,DATA,exps,force_fresh=False)),
    ]
    for fname,fn in tasks:
      p=d/fname
      if file_ready(p): continue
      write_status(state='running',symbol=symbol,year=year,active_task=f'{symbol}-{year} {fname}',active_file=str(p))
      fn()

def cleanup(*_):
    PID_FILE.unlink(missing_ok=True)

def main():
    global last_queue_load_time
    if PID_FILE.exists():
      try:
        pid=int(PID_FILE.read_text().strip())
        if is_running(pid): write_status(state='already_running',pid=pid); return
      except Exception: pass
      PID_FILE.unlink(missing_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    signal.signal(signal.SIGTERM, cleanup); signal.signal(signal.SIGINT, cleanup)
    if not dl.check_terminal(): write_status(state='error',error='terminal_unreachable'); cleanup(); return

    iteration = 0
    while True:
      # Force queue reload every RELOAD_INTERVAL iterations
      if iteration % RELOAD_INTERVAL == 0:
        last_queue_load_time = 0  # Invalidate cache

      nm=next_missing()
      if not nm: write_status(state='complete',active_task='all requested years complete'); cleanup(); return
      s,y,_=nm
      run_year(s,y)
      iteration += 1

if __name__=='__main__': main()
