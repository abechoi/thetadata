# ThetaData Downloader

Download historical options and stock data from your [ThetaData](https://thetadata.net) terminal into local CSV files.

## Requirements

- Python 3.10+
- [ThetaData Terminal v3](https://thetadata.net) running locally (port 25503)
- A Standard or higher ThetaData subscription for Greeks / IV data

## Setup (run once per machine)

```bash
# 1. Clone the repo
git clone https://github.com/abechoi/thetadata.git
cd thetadata

# 2. Create a virtual environment
python3 -m venv .venv

# 3. Install dependencies
.venv/bin/pip install -r requirements.txt
```

## Quick Start - Starting Services

```bash
# Start everything (Terminal + Worker) with one command:
./start.sh

# Check status of services:
./start.sh --status

# Stop all services:
./start.sh --stop

# Or manually start:
./scripts/start_thetadata_singleton.sh  # Starts terminal + worker

# Or use interactive UI instead:
.venv/bin/streamlit run app.py --server.fileWatcherType none
```

## Quick Command Reference

### Live Monitoring
```bash
# Watch downloads in real-time with progress, ETA, and queue
python3 monitor.py

# Faster refresh rate (every 1 second)
python3 monitor.py --refresh 1
```

### Queue Management
```bash
# Add symbols to download queue
python3 queue_manager.py add MSFT --years 2024,2025 --priority 1
python3 queue_manager.py add GOOGL --years 2024

# View queue
python3 queue_manager.py list
python3 queue_manager.py status

# Remove symbol
python3 queue_manager.py remove MSFT

# Pause/resume
python3 queue_manager.py pause
python3 queue_manager.py resume
```

### Inventory & Validation
```bash
# View all downloads
python3 inventory.py summary
python3 inventory.py list AAPL 2024

# Find incomplete downloads
python3 inventory.py gaps

# Validate data integrity
python3 inventory.py validate AAPL 2024

# Export inventory
python3 inventory.py export --format json
```

See [QUEUE_AND_INVENTORY_GUIDE.md](QUEUE_AND_INVENTORY_GUIDE.md) for detailed documentation.

## Features

**Standard data**
- **Options EOD** — daily OHLCV for every contract
- **Options Open Interest** — daily OI per contract
- **Options Trades** — tick-level trade data (large)
- **Stock EOD** — daily OHLCV for the underlying
- **Stock Trades** — tick-level stock trades (large)

**Greeks**
- **Hourly IV** — hourly implied volatility for all contracts, pulled from the `/option/history/greeks/implied_volatility` endpoint

**Utilities**
- **Resume support** — interrupted downloads automatically pick up where they left off
- **Re-filter locally** — once `iv_hourly.csv` is downloaded, re-apply any threshold instantly without hitting the API

## Output structure

```
data/
  AAPL/
    2025/
      options_eod.csv
      options_open_interest.csv
      options_trades.csv
      stock_eod.csv
      stock_trades.csv
      iv_hourly.csv          ← raw hourly IV for all contracts
```
