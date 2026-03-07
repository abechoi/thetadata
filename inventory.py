#!/usr/bin/env python3
"""
ThetaData Inventory & Validation System

Scan, validate, and analyze downloaded ThetaData files.

Usage:
    python inventory.py list [SYMBOL] [YEAR]       # List files with metadata
    python inventory.py summary                      # Quick summary
    python inventory.py validate SYMBOL YEAR         # Validate against API
    python inventory.py gaps                         # Find incomplete downloads
    python inventory.py export [--format json|csv]   # Export inventory
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import sqlite3

# Import downloader for API validation
sys.path.insert(0, str(Path(__file__).parent))
import downloader as dl

# Project paths
ROOT = Path(__file__).parent
DATA_DIR = ROOT / 'data'
CACHE_DIR = ROOT / '.inventory_cache'
CACHE_DIR.mkdir(exist_ok=True)
DB_FILE = CACHE_DIR / 'inventory.db'
VALIDATION_CACHE = CACHE_DIR / 'validation_cache.json'

# Expected file types
REQUIRED_FILES = [
    'options_eod.csv',
    'options_open_interest.csv',
    'options_trades.csv',
    'stock_eod.csv',
    'stock_trades.csv',
    'iv_hourly.csv',
    'iv_spikes.csv'
]


def human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def count_csv_rows(file_path: Path, fast_mode: bool = False) -> int:
    """Count rows in CSV file (excluding header)."""
    if not file_path.exists() or file_path.stat().st_size == 0:
        return 0

    # In fast mode, skip row counting for large files
    if fast_mode and file_path.stat().st_size > 100_000_000:  # > 100MB
        return -2  # Indicates "not counted"

    try:
        with open(file_path, 'r') as f:
            # Skip header
            next(f, None)
            return sum(1 for _ in f)
    except Exception:
        return -1  # Error reading file


def scan_symbol_year(symbol: str, year: int, fast_mode: bool = True, show_progress: bool = False) -> Dict:
    """Scan a single symbol/year directory."""
    symbol_dir = DATA_DIR / symbol / str(year)

    if not symbol_dir.exists():
        return {
            'symbol': symbol,
            'year': year,
            'status': 'missing',
            'files': [],
            'total_size': 0,
            'complete': 0,
            'missing': len(REQUIRED_FILES),
            'partial': 0
        }

    files_info = []
    total_size = 0
    complete_count = 0
    partial_count = 0

    for filename in REQUIRED_FILES:
        if show_progress:
            print(f"  Scanning {symbol}/{year}/{filename}...", end='\r')

        file_path = symbol_dir / filename

        if file_path.exists():
            size = file_path.stat().st_size
            rows = count_csv_rows(file_path, fast_mode=fast_mode)

            # Determine status
            if size == 0 or rows == 0:
                status = 'empty'
                partial_count += 1
            elif rows == -1:
                status = 'error'
                partial_count += 1
            elif rows == -2:
                # Fast mode - file exists and has size, assume complete
                status = 'complete'
                complete_count += 1
                rows = -2  # Mark as not counted
            else:
                status = 'complete'
                complete_count += 1

            files_info.append({
                'name': filename,
                'size': size,
                'size_human': human_size(size),
                'rows': rows if rows >= 0 else None,
                'status': status,
                'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            })
            total_size += size
        else:
            files_info.append({
                'name': filename,
                'size': 0,
                'size_human': '0 B',
                'rows': 0,
                'status': 'missing',
                'modified': None
            })

    if show_progress:
        print(" " * 80, end='\r')  # Clear progress line

    # Determine overall status
    missing_count = len(REQUIRED_FILES) - complete_count - partial_count
    if complete_count == len(REQUIRED_FILES):
        overall_status = 'complete'
    elif complete_count == 0:
        overall_status = 'missing'
    else:
        overall_status = 'partial'

    return {
        'symbol': symbol,
        'year': year,
        'status': overall_status,
        'files': files_info,
        'total_size': total_size,
        'total_size_human': human_size(total_size),
        'complete': complete_count,
        'missing': missing_count,
        'partial': partial_count
    }


def scan_all(fast_mode: bool = True, show_progress: bool = True) -> List[Dict]:
    """Scan all symbol/year combinations in data directory."""
    results = []

    if not DATA_DIR.exists():
        return results

    # Count total directories first for progress
    total_dirs = 0
    for symbol_dir in DATA_DIR.iterdir():
        if symbol_dir.is_dir():
            total_dirs += sum(1 for y in symbol_dir.iterdir() if y.is_dir())

    if show_progress:
        print(f"Scanning {total_dirs} symbol-year directories...")

    current = 0
    # Iterate through all symbol directories
    for symbol_dir in sorted(DATA_DIR.iterdir()):
        if not symbol_dir.is_dir():
            continue

        symbol = symbol_dir.name

        # Iterate through all year directories
        for year_dir in sorted(symbol_dir.iterdir()):
            if not year_dir.is_dir():
                continue

            current += 1
            if show_progress:
                print(f"[{current}/{total_dirs}] Scanning {symbol}/{year_dir.name}...", end='\r')

            try:
                year = int(year_dir.name)
                result = scan_symbol_year(symbol, year, fast_mode=fast_mode, show_progress=False)
                results.append(result)
            except ValueError:
                # Not a year directory
                continue

    if show_progress:
        print(" " * 80, end='\r')  # Clear progress line
        print(f"✓ Scanned {len(results)} symbol-year combinations")

    return results


def list_inventory(symbol: Optional[str] = None, year: Optional[int] = None, fast_mode: bool = True):
    """List inventory with optional filtering."""
    if symbol and year:
        # Single symbol/year - always use slow mode for detail
        results = [scan_symbol_year(symbol.upper(), year, fast_mode=False)]
    elif symbol:
        # All years for a symbol
        symbol = symbol.upper()
        symbol_dir = DATA_DIR / symbol
        if not symbol_dir.exists():
            print(f"No data found for {symbol}", file=sys.stderr)
            return

        results = []
        for year_dir in sorted(symbol_dir.iterdir()):
            if year_dir.is_dir():
                try:
                    y = int(year_dir.name)
                    results.append(scan_symbol_year(symbol, y, fast_mode=fast_mode))
                except ValueError:
                    continue
    else:
        # All symbols and years
        results = scan_all(fast_mode=fast_mode)

    # Print results
    for result in results:
        status_icon = {
            'complete': '✓',
            'partial': '⚠',
            'missing': '✗'
        }.get(result['status'], '?')

        print(f"\n{status_icon} {result['symbol']}/{result['year']}/")

        for file_info in result['files']:
            file_status_icon = {
                'complete': '✓',
                'empty': '⚠',
                'error': '✗',
                'missing': '✗'
            }.get(file_info['status'], '?')

            if file_info['status'] == 'missing':
                print(f"  {file_status_icon} {file_info['name']:<30} MISSING")
            elif file_info['status'] == 'empty':
                print(f"  {file_status_icon} {file_info['name']:<30} 0 B (EMPTY)")
            elif file_info['status'] == 'error':
                print(f"  {file_status_icon} {file_info['name']:<30} ERROR")
            else:
                if file_info['rows'] is None:
                    # Fast mode - show size only
                    print(f"  {file_status_icon} {file_info['name']:<30} {'[not counted]':>12}      {file_info['size_human']:>10}")
                else:
                    rows_str = f"{file_info['rows']:,}" if file_info['rows'] > 0 else "0"
                    print(f"  {file_status_icon} {file_info['name']:<30} {rows_str:>12} rows  {file_info['size_human']:>10}")

        print(f"  Status: {result['status'].upper()} ({result['complete']}/{len(REQUIRED_FILES)} files, {result['total_size_human']})")


def show_summary(fast_mode: bool = True):
    """Show quick summary of all data."""
    results = scan_all(fast_mode=fast_mode, show_progress=True)

    if not results:
        print("No data found")
        return

    # Calculate statistics
    total_symbols = len(set(r['symbol'] for r in results))
    total_years = len(results)
    complete_years = sum(1 for r in results if r['status'] == 'complete')
    partial_years = sum(1 for r in results if r['status'] == 'partial')
    missing_years = sum(1 for r in results if r['status'] == 'missing')
    total_size = sum(r['total_size'] for r in results)
    total_files = sum(r['complete'] for r in results)
    expected_files = len(results) * len(REQUIRED_FILES)

    print(f"\n📊 ThetaData Inventory Summary\n")
    print(f"Symbols:        {total_symbols}")
    print(f"Symbol-Years:   {total_years}")
    print(f"  Complete:     {complete_years} ({complete_years/total_years*100:.1f}%)")
    print(f"  Partial:      {partial_years} ({partial_years/total_years*100:.1f}%)")
    print(f"  Missing:      {missing_years} ({missing_years/total_years*100:.1f}%)")
    print(f"\nFiles:          {total_files}/{expected_files} ({total_files/expected_files*100:.1f}%)")
    print(f"Total Size:     {human_size(total_size)}")

    # Group by symbol
    by_symbol = {}
    for r in results:
        if r['symbol'] not in by_symbol:
            by_symbol[r['symbol']] = []
        by_symbol[r['symbol']].append(r)

    print(f"\n📂 By Symbol:")
    for symbol in sorted(by_symbol.keys()):
        symbol_results = by_symbol[symbol]
        symbol_complete = sum(1 for r in symbol_results if r['status'] == 'complete')
        symbol_size = sum(r['total_size'] for r in symbol_results)
        print(f"  {symbol:<8} {symbol_complete}/{len(symbol_results)} years  {human_size(symbol_size):>10}")


def find_gaps(fast_mode: bool = True):
    """Find incomplete/missing downloads."""
    results = scan_all(fast_mode=fast_mode, show_progress=True)

    gaps = []
    for result in results:
        if result['status'] != 'complete':
            gaps.append(result)

    if not gaps:
        print("✓ No gaps found! All downloads are complete.")
        return

    print(f"\n⚠ Found {len(gaps)} incomplete symbol-year combinations:\n")

    for gap in gaps:
        print(f"{gap['symbol']}/{gap['year']}:")

        for file_info in gap['files']:
            if file_info['status'] != 'complete':
                status_msg = {
                    'missing': 'MISSING',
                    'empty': f'EMPTY (0 bytes)',
                    'error': 'ERROR (corrupted)'
                }.get(file_info['status'], 'UNKNOWN')

                print(f"  - {file_info['name']}: {status_msg}")

    print(f"\n💡 Recommended Action:")
    print(f"   Re-run downloads for the above symbol-year combinations")


def export_inventory(format: str = 'json'):
    """Export inventory to file."""
    results = scan_all()

    if format == 'json':
        output_file = ROOT / 'inventory_export.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"✓ Exported to {output_file}")

    elif format == 'csv':
        output_file = ROOT / 'inventory_export.csv'
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Symbol', 'Year', 'File', 'Status', 'Rows', 'Size', 'Modified'])

            for result in results:
                for file_info in result['files']:
                    writer.writerow([
                        result['symbol'],
                        result['year'],
                        file_info['name'],
                        file_info['status'],
                        file_info['rows'],
                        file_info['size'],
                        file_info['modified']
                    ])

        print(f"✓ Exported to {output_file}")


def load_validation_cache() -> Dict:
    """Load cached validation results."""
    if not VALIDATION_CACHE.exists():
        return {}

    try:
        with open(VALIDATION_CACHE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_validation_cache(cache: Dict):
    """Save validation results to cache."""
    try:
        with open(VALIDATION_CACHE, 'w') as f:
            json.dump(cache, f, indent=2)
    except IOError:
        pass


def validate_symbol_year(symbol: str, year: int, use_cache: bool = True) -> Dict:
    """
    Validate downloaded data against API expectations.

    Returns validation report with:
    - expected_expirations: list of expirations from API
    - found_expirations: list of expirations in downloaded data
    - missing_expirations: expirations not found
    - validation_status: 'complete', 'partial', or 'failed'
    """
    cache = load_validation_cache()
    cache_key = f"{symbol}_{year}"

    # Check cache first
    if use_cache and cache_key in cache:
        cached = cache[cache_key]
        age_seconds = time.time() - cached.get('timestamp', 0)
        # Use cache if less than 1 hour old
        if age_seconds < 3600:
            print(f"  Using cached validation ({int(age_seconds/60)} min old)")
            return cached

    print(f"\n🔍 Validating {symbol} {year} against API...")

    # Check if terminal is running
    if not dl.check_terminal():
        print("  ✗ Error: ThetaData terminal not reachable")
        return {
            'status': 'error',
            'error': 'terminal_unreachable'
        }

    # Get expected expirations from API
    print(f"  Querying API for expirations...")
    try:
        all_exps = dl.list_expirations(symbol)
        expected_exps = dl.filter_expirations_by_year(all_exps, year)
    except Exception as e:
        print(f"  ✗ Error querying API: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

    if not expected_exps:
        print(f"  ⚠ No expirations found for {symbol} {year}")
        return {
            'status': 'no_data',
            'expected_expirations': [],
            'timestamp': time.time()
        }

    print(f"  Found {len(expected_exps)} expirations from API")

    # Check downloaded files
    symbol_dir = DATA_DIR / symbol / str(year)
    options_eod_file = symbol_dir / 'options_eod.csv'

    if not options_eod_file.exists():
        result = {
            'status': 'missing',
            'expected_expirations': expected_exps,
            'found_expirations': [],
            'missing_expirations': expected_exps,
            'timestamp': time.time()
        }
    else:
        # Read downloaded data to find expirations
        try:
            import pandas as pd
            df = pd.read_csv(options_eod_file)

            # Get unique expirations from downloaded data
            if 'ms_of_day' in df.columns:
                # Options data format
                found_exps = sorted(df['ms_of_day'].astype(str).str[:10].unique().tolist())
            else:
                # Try to infer expiration column
                found_exps = []

            missing_exps = [exp for exp in expected_exps if exp not in found_exps]

            if not missing_exps:
                validation_status = 'complete'
            elif found_exps:
                validation_status = 'partial'
            else:
                validation_status = 'failed'

            result = {
                'status': validation_status,
                'expected_expirations': expected_exps,
                'found_expirations': found_exps,
                'missing_expirations': missing_exps,
                'expected_count': len(expected_exps),
                'found_count': len(found_exps),
                'missing_count': len(missing_exps),
                'completeness_pct': (len(found_exps) / len(expected_exps) * 100) if expected_exps else 0,
                'timestamp': time.time()
            }
        except Exception as e:
            result = {
                'status': 'error',
                'error': f'Failed to read file: {e}',
                'timestamp': time.time()
            }

    # Cache the result
    cache[cache_key] = result
    save_validation_cache(cache)

    # Print summary
    if result['status'] == 'complete':
        print(f"  ✓ Complete: All {result['expected_count']} expirations found")
    elif result['status'] == 'partial':
        pct = result.get('completeness_pct', 0)
        print(f"  ⚠ Partial: {result['found_count']}/{result['expected_count']} expirations ({pct:.1f}%)")
        print(f"    Missing: {result['missing_count']} expirations")
    elif result['status'] == 'missing':
        print(f"  ✗ Missing: File not found, expected {len(expected_exps)} expirations")
    elif result['status'] == 'no_data':
        print(f"  ⚠ No data available from API")

    return result


def validate_command(symbol: str, year: int):
    """Run validation command."""
    result = validate_symbol_year(symbol.upper(), year, use_cache=False)

    # Show detailed results
    if result['status'] in ['complete', 'partial']:
        print(f"\n📊 Validation Details:")
        print(f"  Expected: {result['expected_count']} expirations")
        print(f"  Found:    {result['found_count']} expirations")
        print(f"  Missing:  {result['missing_count']} expirations")
        print(f"  Complete: {result['completeness_pct']:.1f}%")

        if result['missing_expirations'] and len(result['missing_expirations']) <= 10:
            print(f"\n  Missing expirations:")
            for exp in result['missing_expirations']:
                print(f"    - {exp}")
        elif result['missing_expirations']:
            print(f"\n  Missing expirations (first 10):")
            for exp in result['missing_expirations'][:10]:
                print(f"    - {exp}")
            print(f"    ... and {len(result['missing_expirations']) - 10} more")


def main():
    parser = argparse.ArgumentParser(description="ThetaData Inventory & Validation")
    parser.add_argument('--slow', action='store_true', help='Count rows in all files (slower but more accurate)')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # List command
    list_parser = subparsers.add_parser('list', help='List inventory')
    list_parser.add_argument('symbol', nargs='?', help='Symbol to list (optional)')
    list_parser.add_argument('year', nargs='?', type=int, help='Year to list (optional)')

    # Summary command
    subparsers.add_parser('summary', help='Show summary statistics')

    # Gaps command
    subparsers.add_parser('gaps', help='Find incomplete downloads')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export inventory')
    export_parser.add_argument('--format', choices=['json', 'csv'], default='json', help='Export format')

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate against API')
    validate_parser.add_argument('symbol', help='Symbol to validate')
    validate_parser.add_argument('year', type=int, help='Year to validate')
    validate_parser.add_argument('--no-cache', action='store_true', help='Skip cache, always query API')

    args = parser.parse_args()

    # Determine fast mode (default True, False if --slow flag)
    fast_mode = not args.slow

    if args.command == 'list':
        list_inventory(args.symbol, args.year, fast_mode=fast_mode)

    elif args.command == 'summary':
        show_summary(fast_mode=fast_mode)

    elif args.command == 'gaps':
        find_gaps(fast_mode=fast_mode)

    elif args.command == 'export':
        export_inventory(args.format)

    elif args.command == 'validate':
        validate_command(args.symbol, args.year)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
