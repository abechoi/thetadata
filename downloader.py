"""
ThetaData v3 downloader — core API client and download functions.
Terminal must be running at http://127.0.0.1:25503 before use.
"""

import json
import time
import calendar
import logging
from io import StringIO
from pathlib import Path
from typing import Callable, Optional

import requests
import pandas as pd

logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:25503/v3"
REQUEST_DELAY = 0.15   # seconds between requests
MAX_RETRIES = 4

ProgressCB = Callable[[int, int, str], None]  # (current, total, label)


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------

def check_terminal() -> bool:
    """Return True if the ThetaData terminal is reachable."""
    try:
        r = requests.get(f"{BASE_URL}/stock/list/symbols", timeout=5, params={"format": "csv"})
        return r.status_code in (200, 472)  # 472 = no data but terminal is up
    except requests.exceptions.ConnectionError:
        return False


def _get(endpoint: str, params: dict) -> Optional[pd.DataFrame]:
    """
    GET request with retry / back-off. Returns a DataFrame on success,
    None if there is no data (404/472) or an unrecoverable error.
    """
    params = {**params, "format": "csv"}
    url = f"{BASE_URL}{endpoint}"

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=60)

            if r.status_code == 200:
                text = r.text.strip()
                if not text or text.startswith("No data"):
                    return None
                return pd.read_csv(StringIO(text))

            elif r.status_code == 429:
                wait = 2 ** attempt
                logger.warning("Rate limited — sleeping %ds", wait)
                time.sleep(wait)
                continue

            elif r.status_code in (404, 472, 473):
                return None

            elif r.status_code == 470:
                logger.error("Plan does not include this endpoint: %s", endpoint)
                return None

            else:
                logger.error("HTTP %s from %s: %s", r.status_code, url, r.text[:200])
                return None

        except requests.exceptions.Timeout:
            logger.warning("Timeout on attempt %d — %s", attempt + 1, url)
        except Exception as exc:
            logger.error("Unexpected error: %s", exc)
            return None

        time.sleep(REQUEST_DELAY)

    logger.error("Giving up after %d attempts: %s", MAX_RETRIES, url)
    return None


# ---------------------------------------------------------------------------
# Checkpoint helpers  (hidden .json files alongside the CSVs)
# ---------------------------------------------------------------------------

def _ckpt_load(path: Path) -> set:
    """Return the set of already-completed step keys, or empty set."""
    if path.exists():
        try:
            return set(json.loads(path.read_text()))
        except Exception:
            return set()
    return set()


def _ckpt_save(path: Path, completed: set) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(completed)))


def _ckpt_clear(path: Path) -> None:
    if path.exists():
        path.unlink()


def get_checkpoint_status(symbol: str, year: int, output_dir: Path) -> dict[str, int]:
    """
    Return how many steps are already completed for each download type.
    Used by the UI to show resume status before the user clicks Download.
    Returns e.g. {"iv_spikes": 143, "options_eod": 32}
    """
    base = output_dir / symbol / str(year)
    names = ["options_eod", "options_oi", "options_trades", "iv_spikes", "stock_trades"]
    return {
        name: len(_ckpt_load(base / f".{name}_ckpt.json"))
        for name in names
        if (base / f".{name}_ckpt.json").exists()
    }


# ---------------------------------------------------------------------------
# List helpers
# ---------------------------------------------------------------------------

def list_expirations(symbol: str) -> list[str]:
    """Return all expiration dates for a symbol as 'YYYY-MM-DD' strings."""
    df = _get("/option/list/expirations", {"symbol": symbol})
    if df is None or df.empty:
        return []
    # Response columns: symbol, expiration
    col = "expiration" if "expiration" in df.columns else df.columns[-1]
    return [str(v) for v in df[col].tolist()]


def filter_expirations_by_year(expirations: list[str], year: int) -> list[str]:
    """Return only expirations whose date falls in the given year."""
    result = []
    for exp in expirations:
        try:
            if int(str(exp).replace("-", "")[:4]) == year:
                result.append(exp)
        except (ValueError, TypeError):
            pass
    return sorted(result)


# ---------------------------------------------------------------------------
# File save helper
# ---------------------------------------------------------------------------

def _save(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        df.to_csv(path, mode="a", header=False, index=False)
    else:
        df.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Download functions — all support force_fresh + checkpoint resume
# ---------------------------------------------------------------------------

def download_options_eod(
    symbol: str,
    year: int,
    output_dir: Path,
    expirations: list[str],
    force_fresh: bool = False,
    progress_cb: Optional[ProgressCB] = None,
) -> Optional[Path]:
    """Download end-of-day options data for every expiration."""
    out      = output_dir / symbol / str(year) / "options_eod.csv"
    ckpt     = output_dir / symbol / str(year) / ".options_eod_ckpt.json"

    if force_fresh:
        for f in [out, ckpt]:
            if f.exists(): f.unlink()

    completed = _ckpt_load(ckpt)
    rows_written = 0

    for i, exp in enumerate(expirations):
        if exp in completed:
            if progress_cb:
                progress_cb(i + 1, len(expirations), f"Skip (done)  {exp}")
            continue

        if progress_cb:
            progress_cb(i, len(expirations), f"EOD  {exp}")

        df = _get("/option/history/eod", {
            "symbol": symbol,
            "expiration": exp,
            "start_date": f"{year}-01-01",
            "end_date": exp,
            "strike": "*",
            "right": "both",
        })

        if df is not None and not df.empty:
            _save(df, out)
            rows_written += len(df)

        completed.add(exp)
        _ckpt_save(ckpt, completed)
        time.sleep(REQUEST_DELAY)

    if progress_cb:
        progress_cb(len(expirations), len(expirations), "Done")
    _ckpt_clear(ckpt)
    return out if out.exists() else None


def download_options_trades(
    symbol: str,
    year: int,
    output_dir: Path,
    expirations: list[str],
    force_fresh: bool = False,
    progress_cb: Optional[ProgressCB] = None,
) -> Optional[Path]:
    """Download tick-level option trades per expiration. Can be very large."""
    out  = output_dir / symbol / str(year) / "options_trades.csv"
    ckpt = output_dir / symbol / str(year) / ".options_trades_ckpt.json"

    if force_fresh:
        for f in [out, ckpt]:
            if f.exists(): f.unlink()

    completed = _ckpt_load(ckpt)
    rows_written = 0

    for i, exp in enumerate(expirations):
        if exp in completed:
            if progress_cb:
                progress_cb(i + 1, len(expirations), f"Skip (done)  {exp}")
            continue

        if progress_cb:
            progress_cb(i, len(expirations), f"Trades  {exp}")

        df = _get("/option/history/trade", {
            "symbol": symbol,
            "expiration": exp,
            "start_date": f"{year}-01-01",
            "end_date": exp,
            "strike": "*",
            "right": "both",
        })

        if df is not None and not df.empty:
            _save(df, out)
            rows_written += len(df)

        completed.add(exp)
        _ckpt_save(ckpt, completed)
        time.sleep(REQUEST_DELAY)

    if progress_cb:
        progress_cb(len(expirations), len(expirations), "Done")
    _ckpt_clear(ckpt)
    return out if out.exists() else None


def download_options_open_interest(
    symbol: str,
    year: int,
    output_dir: Path,
    expirations: list[str],
    force_fresh: bool = False,
    progress_cb: Optional[ProgressCB] = None,
) -> Optional[Path]:
    """Download daily open interest for every expiration."""
    out  = output_dir / symbol / str(year) / "options_open_interest.csv"
    ckpt = output_dir / symbol / str(year) / ".options_oi_ckpt.json"

    if force_fresh:
        for f in [out, ckpt]:
            if f.exists(): f.unlink()

    completed = _ckpt_load(ckpt)
    rows_written = 0

    for i, exp in enumerate(expirations):
        if exp in completed:
            if progress_cb:
                progress_cb(i + 1, len(expirations), f"Skip (done)  {exp}")
            continue

        if progress_cb:
            progress_cb(i, len(expirations), f"OI  {exp}")

        df = _get("/option/history/open_interest", {
            "symbol": symbol,
            "expiration": exp,
            "start_date": f"{year}-01-01",
            "end_date": exp,
            "strike": "*",
            "right": "both",
        })

        if df is not None and not df.empty:
            _save(df, out)
            rows_written += len(df)

        completed.add(exp)
        _ckpt_save(ckpt, completed)
        time.sleep(REQUEST_DELAY)

    if progress_cb:
        progress_cb(len(expirations), len(expirations), "Done")
    _ckpt_clear(ckpt)
    return out if out.exists() else None


def download_stock_eod(
    symbol: str,
    year: int,
    output_dir: Path,
    force_fresh: bool = False,
    progress_cb: Optional[ProgressCB] = None,
) -> Optional[Path]:
    """Download stock end-of-day (OHLCV) for the full year in one call."""
    out = output_dir / symbol / str(year) / "stock_eod.csv"
    if force_fresh and out.exists():
        out.unlink()

    if progress_cb:
        progress_cb(0, 1, f"Stock EOD {symbol} {year}")

    df = _get("/stock/history/eod", {
        "symbol": symbol,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
    })

    if progress_cb:
        progress_cb(1, 1, "Done")

    if df is None or df.empty:
        return None
    return _save(df, out)


def download_stock_trades(
    symbol: str,
    year: int,
    output_dir: Path,
    force_fresh: bool = False,
    progress_cb: Optional[ProgressCB] = None,
) -> Optional[Path]:
    """Download tick-level stock trades, one month at a time."""
    out  = output_dir / symbol / str(year) / "stock_trades.csv"
    ckpt = output_dir / symbol / str(year) / ".stock_trades_ckpt.json"

    if force_fresh:
        for f in [out, ckpt]:
            if f.exists(): f.unlink()

    completed = _ckpt_load(ckpt)
    rows_written = 0
    months = list(range(1, 13))

    for i, month in enumerate(months):
        key = f"{year}-{month:02d}"
        if key in completed:
            if progress_cb:
                progress_cb(i + 1, len(months), f"Skip (done)  {key}")
            continue

        last_day = calendar.monthrange(year, month)[1]
        start = f"{year}-{month:02d}-01"
        end   = f"{year}-{month:02d}-{last_day:02d}"

        if progress_cb:
            progress_cb(i, len(months), f"Stock Trades {start} → {end}")

        df = _get("/stock/history/trade", {
            "symbol": symbol,
            "start_date": start,
            "end_date": end,
        })

        if df is not None and not df.empty:
            _save(df, out)
            rows_written += len(df)

        completed.add(key)
        _ckpt_save(ckpt, completed)
        time.sleep(REQUEST_DELAY)

    if progress_cb:
        progress_cb(len(months), len(months), "Done")
    _ckpt_clear(ckpt)
    return out if out.exists() else None


def download_iv_spikes(
    symbol: str,
    year: int,
    output_dir: Path,
    expirations: list[str],
    spike_threshold: float = 0.07,
    force_fresh: bool = False,
    progress_cb: Optional[ProgressCB] = None,
) -> Optional[Path]:
    """
    Download hourly IV for every expiration and detect days where IV swung
    >= spike_threshold within a single trading day (in decimal: 0.07 = 7pp).

    Saves two files:
      iv_hourly.csv  — all raw hourly IV data (reusable for any threshold)
      iv_spikes.csv  — filtered to days meeting the threshold
    """
    out_dir    = output_dir / symbol / str(year)
    out_spikes = out_dir / "iv_spikes.csv"
    out_raw    = out_dir / "iv_hourly.csv"
    ckpt       = out_dir / ".iv_spikes_ckpt.json"

    if force_fresh:
        for f in [out_spikes, out_raw, ckpt]:
            if f.exists(): f.unlink()

    # If the raw output is missing but a checkpoint exists, the previous run
    # was interrupted after the files were cleared — reset so we re-download.
    if not out_raw.exists() and ckpt.exists():
        _ckpt_clear(ckpt)

    completed   = _ckpt_load(ckpt)
    total_steps = len(expirations) * 12
    step        = 0

    for exp in expirations:
        for month in range(1, 13):
            step += 1
            key = f"{exp}_{month:02d}"

            if key in completed:
                if progress_cb:
                    progress_cb(step, total_steps, f"Skip (done)  {exp}  {year}-{month:02d}")
                continue

            last_day = calendar.monthrange(year, month)[1]
            start = f"{year}-{month:02d}-01"
            end   = f"{year}-{month:02d}-{last_day:02d}"

            if progress_cb:
                progress_cb(step, total_steps, f"IV  {exp}  {start[:7]}")

            df = _get("/option/history/greeks/implied_volatility", {
                "symbol": symbol,
                "expiration": exp,
                "interval": "1h",
                "start_date": start,
                "end_date": end,
                "strike": "*",
                "right": "both",
            })

            if df is not None and not df.empty:
                _save(df, out_raw)

                ts_col = "timestamp" if "timestamp" in df.columns else df.columns[4]
                df["date"] = pd.to_datetime(df[ts_col]).dt.date

                grp_cols = ["expiration", "strike", "right", "date"]
                iv_df = df.dropna(subset=["implied_vol"])

                if not iv_df.empty:
                    daily = (
                        iv_df.groupby(grp_cols)["implied_vol"]
                        .agg(iv_open="first", iv_high="max", iv_low="min", iv_close="last")
                        .reset_index()
                    )
                    daily["iv_swing"] = daily["iv_high"] - daily["iv_low"]
                    daily["symbol"]   = symbol

                    if "underlying_price" in iv_df.columns:
                        up = (
                            iv_df.groupby(grp_cols)["underlying_price"]
                            .last()
                            .rename("underlying_price_close")
                            .reset_index()
                        )
                        daily = daily.merge(up, on=grp_cols, how="left")

                    spikes = daily[daily["iv_swing"] >= spike_threshold].copy()
                    if not spikes.empty:
                        cols = ["date", "symbol", "expiration", "strike", "right",
                                "iv_open", "iv_high", "iv_low", "iv_close", "iv_swing"]
                        if "underlying_price_close" in spikes.columns:
                            cols.append("underlying_price_close")
                        _save(spikes[cols], out_spikes)

            completed.add(key)
            _ckpt_save(ckpt, completed)
            time.sleep(REQUEST_DELAY)

    if progress_cb:
        progress_cb(total_steps, total_steps, "Done")
    _ckpt_clear(ckpt)
    return out_raw if out_raw.exists() else None
