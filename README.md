# ThetaData Downloader

Download historical options and stock data from your [ThetaData](https://thetadata.net) terminal into local CSV files.

## Requirements

- Python 3.10+
- [ThetaData Terminal v3](https://thetadata.net) running locally (port 25503)
- A Standard or higher ThetaData subscription for Greeks / IV data

## Setup (run once per machine)

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd thetadata

# 2. Create a virtual environment
python3 -m venv .venv

# 3. Install dependencies
.venv/bin/pip install -r requirements.txt
```

## Running the app

```bash
# Start ThetaData Terminal first, then:
.venv/bin/streamlit run app.py --server.fileWatcherType none
```

The `--server.fileWatcherType none` flag prevents Streamlit from restarting the app
if you edit code while a download is running.

## Features

- **Options EOD** — daily OHLCV for every contract
- **Options Open Interest** — daily OI per contract
- **Options Trades** — tick-level trade data (large)
- **Stock EOD** — daily OHLCV for the underlying
- **Stock Trades** — tick-level stock trades (large)
- **IV Spike Detection** — hourly implied volatility, flags days where IV moved ≥ N percentage points intraday
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
      iv_hourly.csv          ← all raw hourly IV (reusable)
      iv_spikes.csv          ← filtered to your threshold
      iv_spikes_5.0pct.csv   ← re-filtered copies at different thresholds
```
