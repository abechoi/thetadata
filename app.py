"""
ThetaData Downloader — Streamlit UI
Run with:  .venv/bin/streamlit run app.py --server.fileWatcherType none
"""

from pathlib import Path

import streamlit as st

import downloader as dl

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="ThetaData Downloader",
    page_icon="📈",
    layout="wide",
)

st.title("📈 ThetaData Downloader")
st.caption("Download historical options and stock data from your ThetaData terminal.")

# ---------------------------------------------------------------------------
# Terminal connection check
# ---------------------------------------------------------------------------

if dl.check_terminal():
    st.success("ThetaData Terminal is connected at 127.0.0.1:25503")
else:
    st.error(
        "Cannot reach ThetaData Terminal at 127.0.0.1:25503.  "
        "Make sure the terminal app is running, then refresh this page."
    )
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# Sidebar — configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Settings")

    symbol = st.text_input("Ticker symbol", value="AAPL").strip().upper()

    year = st.number_input("Year", min_value=2005, max_value=2025, value=2025, step=1)

    st.subheader("Standard data")
    dl_options_eod    = st.checkbox("Options EOD", value=True,
        help="Daily open/high/low/close/volume for every options contract")
    dl_options_oi     = st.checkbox("Options Open Interest", value=True,
        help="Daily open interest per contract")
    dl_options_trades = st.checkbox("Options Trades (tick-level)", value=False,
        help="Every trade tick — can be very large.")
    dl_stock_eod      = st.checkbox("Stock EOD", value=True,
        help="Daily OHLCV for the underlying stock")
    dl_stock_trades   = st.checkbox("Stock Trades (tick-level)", value=False,
        help="Every stock trade tick, downloaded month by month.")

    st.subheader("Greeks")
    dl_iv_spikes = st.checkbox("Hourly IV", value=False,
        help="Download hourly implied volatility for all contracts.")
    spike_threshold = 0.0

    st.subheader("Resume / Fresh start")
    force_fresh = st.checkbox(
        "Force fresh download (ignore saved progress)",
        value=False,
        help="By default, interrupted downloads resume where they left off. "
             "Check this to start completely over and overwrite existing files.",
    )

    st.subheader("Output directory")
    default_out    = str(Path.home() / "Projects" / "thetadata" / "data")
    output_dir_str = st.text_input("", value=default_out)
    output_dir     = Path(output_dir_str)

# ---------------------------------------------------------------------------
# Main area — preview + resume status + download
# ---------------------------------------------------------------------------

col_preview, col_download = st.columns([1, 1], gap="large")

# ---- Preview ---------------------------------------------------------------
with col_preview:
    st.subheader("Preview")
    if st.button("Fetch expiration list", use_container_width=True):
        with st.spinner(f"Fetching expirations for {symbol}…"):
            all_exps  = dl.list_expirations(symbol)
            year_exps = dl.filter_expirations_by_year(all_exps, year)

        if not year_exps:
            st.warning(f"No expirations found for **{symbol}** in **{year}**.")
        else:
            st.info(
                f"**{symbol}** has **{len(year_exps)} expirations** in **{year}** "
                f"(earliest: {year_exps[0]}, latest: {year_exps[-1]})"
            )
            if dl_iv_spikes:
                n_calls = len(year_exps) * 12
                st.caption(f"IV spike scan: ~{n_calls:,} API calls ({len(year_exps)} exp × 12 months)")

            st.session_state["expirations"] = year_exps
            st.session_state["symbol"]      = symbol
            st.session_state["year"]        = year

            with st.expander("Show all expirations"):
                st.write(year_exps)

    # Show resume status if checkpoints exist
    ckpt_status = dl.get_checkpoint_status(symbol, year, output_dir)
    if ckpt_status and not force_fresh:
        st.subheader("In-progress downloads detected")
        for name, count in ckpt_status.items():
            label = name.replace("_", " ").title()
            st.info(f"**{label}**: {count} steps already completed — will resume")
        st.caption("Uncheck 'Force fresh download' in the sidebar to resume, or check it to restart.")

# ---- Download --------------------------------------------------------------
with col_download:
    st.subheader("Download")

    nothing_selected = not any([
        dl_options_eod, dl_options_oi, dl_options_trades,
        dl_stock_eod, dl_stock_trades, dl_iv_spikes,
    ])

    if nothing_selected:
        st.info("Select at least one data type in the sidebar.")
    elif st.button("Start download", type="primary", use_container_width=True):

        needs_exps  = any([dl_options_eod, dl_options_oi, dl_options_trades, dl_iv_spikes])
        expirations = st.session_state.get("expirations", [])

        if needs_exps and (
            not expirations
            or st.session_state.get("symbol") != symbol
            or st.session_state.get("year")   != year
        ):
            with st.spinner("Fetching expirations…"):
                all_exps    = dl.list_expirations(symbol)
                expirations = dl.filter_expirations_by_year(all_exps, year)
                st.session_state["expirations"] = expirations
                st.session_state["symbol"]      = symbol
                st.session_state["year"]        = year

        if needs_exps and not expirations:
            st.error(f"No expirations found for {symbol} {year}.")
            st.stop()

        # ------------------------------------------------------------------
        # Run downloads
        # ------------------------------------------------------------------
        results      = {}
        progress_bar = st.progress(0.0)
        status_text  = st.empty()

        def make_progress(label: str, total_tasks: int, task_index: int):
            def cb(current: int, total: int, step_label: str):
                try:
                    overall = (task_index + (current / max(total, 1))) / total_tasks
                    progress_bar.progress(min(overall, 1.0))
                    status_text.text(f"{label}: {step_label}  ({current}/{total})")
                except Exception:
                    pass
            return cb

        task_list = []
        if dl_options_eod:    task_list.append("options_eod")
        if dl_options_oi:     task_list.append("options_oi")
        if dl_options_trades: task_list.append("options_trades")
        if dl_stock_eod:      task_list.append("stock_eod")
        if dl_stock_trades:   task_list.append("stock_trades")
        if dl_iv_spikes:      task_list.append("iv_spikes")

        n = len(task_list)

        for idx, task in enumerate(task_list):
            cb = make_progress(task.replace("_", " ").title(), n, idx)
            try:
                if task == "options_eod":
                    results["Options EOD"] = dl.download_options_eod(
                        symbol, year, output_dir, expirations,
                        force_fresh=force_fresh, progress_cb=cb)

                elif task == "options_oi":
                    results["Options Open Interest"] = dl.download_options_open_interest(
                        symbol, year, output_dir, expirations,
                        force_fresh=force_fresh, progress_cb=cb)

                elif task == "options_trades":
                    results["Options Trades"] = dl.download_options_trades(
                        symbol, year, output_dir, expirations,
                        force_fresh=force_fresh, progress_cb=cb)

                elif task == "stock_eod":
                    results["Stock EOD"] = dl.download_stock_eod(
                        symbol, year, output_dir,
                        force_fresh=force_fresh, progress_cb=cb)

                elif task == "stock_trades":
                    results["Stock Trades"] = dl.download_stock_trades(
                        symbol, year, output_dir,
                        force_fresh=force_fresh, progress_cb=cb)

                elif task == "iv_spikes":
                    results["Hourly IV"] = dl.download_iv_spikes(
                        symbol, year, output_dir, expirations,
                        spike_threshold=spike_threshold,
                        force_fresh=force_fresh, progress_cb=cb)

            except Exception as e:
                label = task.replace("_", " ").title()
                st.warning(f"**{label}** failed: {e}")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        progress_bar.progress(1.0)
        status_text.text("All done!")
        st.divider()
        st.subheader("Results")

        for label, path in results.items():
            if path and path.exists():
                size_bytes = path.stat().st_size
                size_str   = f"{size_bytes / 1_073_741_824:.2f} GB" if size_bytes >= 1_073_741_824 else f"{size_bytes / 1_048_576:.1f} MB"
                rows       = sum(1 for _ in open(path)) - 1
                st.success(f"**{label}** → `{path}`  ({rows:,} rows, {size_str})")

            else:
                st.warning(f"**{label}** — no data returned (check plan or symbol).")


# ---------------------------------------------------------------------------
# Re-filter IV spikes from local data (no API call needed)
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Re-filter IV spikes from local data")
st.caption("If you already downloaded iv_hourly.csv, apply a new threshold instantly without hitting the API.")

raw_iv_path = output_dir / symbol / str(year) / "iv_hourly.csv"

if raw_iv_path.exists():
    col_a, col_b = st.columns([1, 2])
    with col_a:
        new_threshold_pct = st.number_input(
            "New threshold (percentage points)", min_value=0.5, max_value=100.0,
            value=7.0, step=0.5, key="refilter_threshold"
        )
        if st.button("Apply filter", use_container_width=True):
            import pandas as pd
            new_threshold = new_threshold_pct / 100.0
            with st.spinner("Filtering…"):
                df = pd.read_csv(raw_iv_path)
                ts_col = "timestamp" if "timestamp" in df.columns else df.columns[4]
                df["date"] = pd.to_datetime(df[ts_col]).dt.date
                grp_cols = ["expiration", "strike", "right", "date"]
                iv_df = df.dropna(subset=["implied_vol"])
                daily = (
                    iv_df.groupby(grp_cols)["implied_vol"]
                    .agg(iv_open="first", iv_high="max", iv_low="min", iv_close="last")
                    .reset_index()
                )
                daily["iv_swing"] = daily["iv_high"] - daily["iv_low"]
                daily["symbol"]   = symbol
                spikes = daily[daily["iv_swing"] >= new_threshold].sort_values(
                    "iv_swing", ascending=False
                )

            out_path = output_dir / symbol / str(year) / f"iv_spikes_{new_threshold_pct:.1f}pct.csv"
            spikes.to_csv(out_path, index=False)

            with col_b:
                st.success(f"Found **{len(spikes):,} spike records** at ≥{new_threshold_pct}pp  →  `{out_path}`")
                st.dataframe(spikes.head(20), use_container_width=True)
else:
    st.caption(f"No `iv_hourly.csv` found yet for {symbol} {year}. Run the IV Spike Detection download first.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    f"Output: `{output_dir}`  |  "
    "Interrupted downloads resume automatically on restart (unless 'Force fresh' is checked)."
)
