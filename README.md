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

## Running the app

```bash
# Start ThetaData Terminal first, then:
.venv/bin/streamlit run app.py --server.fileWatcherType none
```

The `--server.fileWatcherType none` flag prevents Streamlit from restarting the app
if you edit code while a download is running.

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
