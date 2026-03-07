# ThetaData Queue & Inventory System Guide

## Overview

Two new systems have been added to manage your ThetaData downloads more effectively:

1. **Dynamic Symbol Queue** - Manage download symbols without editing code
2. **Inventory & Validation** - Track, verify, and analyze downloaded data

---

## 1. Dynamic Symbol Queue

### Quick Start

```bash
# Add a symbol to the queue
python3 queue_manager.py add MSFT --years 2024,2025 --priority 1

# List current queue
python3 queue_manager.py list

# Remove a symbol
python3 queue_manager.py remove MSFT

# View queue status
python3 queue_manager.py status

# Clear entire queue
python3 queue_manager.py clear

# Pause/resume queue processing
python3 queue_manager.py pause
python3 queue_manager.py resume
```

### How It Works

The queue system uses a `queue.json` file to store symbols, years, and priorities. The worker script automatically reads from this queue instead of hardcoded symbol lists.

**Key Features:**
- ✅ Add/remove symbols dynamically
- ✅ Set priorities (1=highest)
- ✅ Specify years per symbol
- ✅ Auto-reload every 10 downloads (workers pick up new symbols automatically)
- ✅ Pause/resume queue processing

### Queue File Format

The `queue.json` file structure:

```json
{
  "active": true,
  "auto_reload": true,
  "symbols": [
    {
      "symbol": "AAPL",
      "years": [2021, 2022, 2023, 2024, 2025],
      "priority": 1
    },
    {
      "symbol": "MSFT",
      "years": [2024, 2025],
      "priority": 2
    }
  ]
}
```

### Examples

**Add multiple symbols:**
```bash
python3 queue_manager.py add AAPL --years 2021,2022,2023,2024,2025 --priority 1
python3 queue_manager.py add NVDA --years 2024,2025 --priority 1
python3 queue_manager.py add TSLA --years 2023,2024 --priority 2
```

**Update existing symbol:**
```bash
# Adding same symbol updates it
python3 queue_manager.py add AAPL --years 2024,2025 --priority 1
```

**Default years:**
```bash
# If --years not specified, defaults to [2021, 2022, 2023, 2024, 2025]
python3 queue_manager.py add SPY
```

---

## 2. Inventory & Validation System

### Quick Start

```bash
# View summary of all downloads
python3 inventory.py summary

# List all files for a symbol
python3 inventory.py list AAPL

# List files for specific symbol/year
python3 inventory.py list AAPL 2024

# Find incomplete downloads
python3 inventory.py gaps

# Validate against API (requires terminal running)
python3 inventory.py validate AAPL 2024

# Export inventory
python3 inventory.py export --format json
python3 inventory.py export --format csv
```

### Features

#### 1. List Inventory

Shows all downloaded files with metadata:

```bash
$ python3 inventory.py list AAPL 2024

✓ AAPL/2024/
  ✓ options_eod.csv                     585,968 rows     68.8 MB
  ✓ options_open_interest.csv           288,290 rows     13.7 MB
  ✓ options_trades.csv                1,464,066 rows    126.3 MB
  ✓ stock_eod.csv                           252 rows     29.1 KB
  ✓ stock_trades.csv                158,836,289 rows      9.1 GB
  ✓ iv_hourly.csv                     3,213,210 rows    344.7 MB
  ✓ iv_spikes.csv                       432,539 rows     29.7 MB
  Status: COMPLETE (7/7 files, 9.6 GB)
```

**Status Icons:**
- ✓ Complete
- ⚠ Partial/Empty
- ✗ Missing/Error

#### 2. Summary

Quick overview of all data:

```bash
$ python3 inventory.py summary

📊 ThetaData Inventory Summary

Symbols:        9
Symbol-Years:   45
  Complete:     12 (26.7%)
  Partial:      15 (33.3%)
  Missing:      18 (40.0%)

Files:          189/315 (60.0%)
Total Size:     127.3 GB

📂 By Symbol:
  AAPL       5/5 years     45.2 GB
  META       3/5 years     28.1 GB
  NVDA       2/5 years     18.7 GB
  ...
```

#### 3. Gap Analysis

Find incomplete/missing downloads:

```bash
$ python3 inventory.py gaps

⚠ Found 15 incomplete symbol-year combinations:

NVDA/2023:
  - options_trades.csv: MISSING
  - stock_trades.csv: EMPTY (0 bytes)

TSLA/2024:
  - iv_spikes.csv: ERROR (corrupted)

💡 Recommended Action:
   Re-run downloads for the above symbol-year combinations
```

#### 4. Validation

Verify downloaded data against API:

```bash
$ python3 inventory.py validate AAPL 2024

🔍 Validating AAPL 2024 against API...
  Querying API for expirations...
  Found 252 expirations from API
  ✓ Complete: All 252 expirations found

📊 Validation Details:
  Expected: 252 expirations
  Found:    252 expirations
  Missing:  0 expirations
  Complete: 100.0%
```

**Validation checks:**
- ✅ Queries API for expected expirations
- ✅ Compares with downloaded data
- ✅ Identifies missing expirations
- ✅ Calculates completeness percentage
- ✅ Caches results for 1 hour

#### 5. Export

Export inventory data:

```bash
# JSON export
python3 inventory.py export --format json
# Creates inventory_export.json

# CSV export
python3 inventory.py export --format csv
# Creates inventory_export.csv
```

---

## Integration with Workers

### Auto-Reload

The `priority_backlog_worker.py` now:
- Reads from `queue.json` instead of hardcoded symbols
- Reloads queue every 10 downloads automatically
- Falls back to hardcoded symbols if queue.json doesn't exist

### Adding Symbols While Running

You can add symbols to the queue while the worker is running:

```bash
# Worker is running and downloading AAPL...

# Add a new symbol
python3 queue_manager.py add MSFT --years 2024

# After current download completes, worker will reload queue
# and pick up MSFT automatically (within ~10 downloads)
```

### Monitoring Progress

Use the inventory system to monitor progress:

```bash
# Quick check
python3 inventory.py summary

# Detailed view
python3 inventory.py list

# Find what's left
python3 inventory.py gaps
```

---

## Workflow Examples

### Example 1: Adding New Symbols

```bash
# 1. Check current queue
python3 queue_manager.py list

# 2. Add new symbols
python3 queue_manager.py add GOOGL --years 2024,2025 --priority 1
python3 queue_manager.py add AMZN --years 2024 --priority 2

# 3. Verify queue
python3 queue_manager.py status

# 4. Worker will pick up new symbols automatically
```

### Example 2: Validating Downloads

```bash
# 1. Check what's downloaded
python3 inventory.py summary

# 2. Find gaps
python3 inventory.py gaps

# 3. Validate specific symbol/year
python3 inventory.py validate AAPL 2024

# 4. If incomplete, add back to queue
python3 queue_manager.py add AAPL --years 2024
```

### Example 3: Cleaning Up Incomplete Downloads

```bash
# 1. Find all gaps
python3 inventory.py gaps > gaps.txt

# 2. Review gaps
cat gaps.txt

# 3. Add incomplete symbol-years back to queue
python3 queue_manager.py add NVDA --years 2023
python3 queue_manager.py add TSLA --years 2024

# 4. Restart worker to re-download
./scripts/priority_backlog_worker.py
```

---

## File Locations

- **Queue file:** `/Users/abe/Projects/thetadata/queue.json`
- **Inventory cache:** `/Users/abe/Projects/thetadata/.inventory_cache/`
- **Data directory:** `/Users/abe/Projects/thetadata/data/`

---

## Tips & Best Practices

1. **Priorities:** Use priority 1 for important symbols, priority 2+ for lower priority
2. **Years:** Only specify years you actually need to save time and space
3. **Validation:** Run validation after downloads complete to verify integrity
4. **Gaps:** Regularly check for gaps and re-add incomplete downloads
5. **Export:** Export inventory periodically for backup/analysis

---

## Troubleshooting

### Queue not loading

**Problem:** Worker not picking up queue changes

**Solution:**
```bash
# Force worker restart
./scripts/kill_thetadata.sh
./scripts/start_thetadata_singleton.sh
```

### Validation fails

**Problem:** "ThetaData terminal not reachable"

**Solution:**
```bash
# Ensure terminal is running
./scripts/start_thetadata_singleton.sh

# Test terminal
curl http://127.0.0.1:25503/v3/stock/list/symbols?format=csv
```

### Missing files

**Problem:** Files show as missing but were downloaded

**Solution:**
```bash
# Check file actually exists
ls -lh /Users/abe/Projects/thetadata/data/AAPL/2024/

# If file is 0 bytes, re-download
python3 queue_manager.py add AAPL --years 2024
```

---

## Migration from Hardcoded Lists

Your existing symbols are already in `queue.json`:
- AAPL, NVDA, NFLX, TSLA, SPY, QQQ, META, MRNA, BNTX
- Years: 2021, 2022, 2023, 2024, 2025
- All priority 1

No action needed! The worker will continue downloading these symbols. You can now add more symbols dynamically.

---

## Summary

**Queue Management:**
```bash
python3 queue_manager.py [add|remove|list|clear|status|pause|resume]
```

**Inventory & Validation:**
```bash
python3 inventory.py [list|summary|gaps|validate|export]
```

Both tools work together to give you full control over your ThetaData downloads.
