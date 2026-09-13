# Data access and file formats

The public repository contains result tables and the frozen input-data manifest. Raw market histories and the full processed return panel are excluded from Git because redistribution permission has not been established; see the [source assessment](../report/sources/provenance.md). The original research brief explicitly requires this reconstruction route when rights are unclear.

## Reconstruct the exact inputs

From the repository root, after `uv sync --locked`:

```bash
uv run --locked python scripts/01_download_data.py
uv run --locked python scripts/02_prepare_data.py
```

Alternatively, `uv run --locked python scripts/run_all.py` downloads the same inputs and performs the full analysis. No API key is required. Later runs can use `--skip-download` with the full pipeline once all eight raw files exist locally.

The [manifest](data_manifest.csv) is the authoritative file-level specification. It pins revision `14fec12f4af23d69633b6fd37e6d477facf0fa2b` of [zjplab/US-Trading-Data](https://github.com/zjplab/US-Trading-Data), records the original 2026-09-12 acquisition, and provides SHA-256 hashes, byte sizes, date coverage, and direct download URLs. All eight series end on 2026-09-11. The original acquisition timestamp is preserved when the exact bytes are downloaded again; the current analysis timestamp is logged separately.

| Local ticker | Upstream file | Role |
|---|---|---|
| BA | `data/SP500/BA.csv` | Boeing outcome and trading volume |
| GSPC | `data/Indexes/^GSPC.csv` | S&P 500 market control |
| RTX, LMT, NOC, GD, TDG, HWM | `data/SP500/{ticker}.csv` | Equal-weight aerospace/defense peer basket |

The downloader fetches and validates the whole batch before writing missing raw files. It rejects changed source bytes and incomplete or tampered local snapshots. Do not replace hashes to suppress an error. Availability of the pinned upstream revision remains an external dependency.

## Locally generated panel

`data/processed/daily_returns.csv` uses the market trading calendar. Returns are simple supplied-Close returns, with no forward filling or extra dividend/split adjustment. Missing closes cannot create a return across multiple trading sessions.

| Column | Meaning / units |
|---|---|
| `date` | Local exchange trading date, `YYYY-MM-DD` |
| `ba_return` | Boeing daily simple return, decimal fraction |
| `market_return` | S&P 500 daily simple return, decimal fraction |
| `peer_return` | Mean of available six-peer returns; at least five required |
| `sector_return` | Peer return minus market return |
| `ba_volume` | Supplied Boeing share volume |

Other ticker-return columns may also be retained. Event windows are indexed on the intact trading calendar, and the model requires complete values within each analysis window.

## Published analysis data

Files under [`outputs/tables/`](../outputs/tables/) contain Bayesian window summaries, event comparisons, OLS results, residual-block placebos, abnormal volume, estimation dates, sampler diagnostics, and the reference audit. Return statistics are **decimal fractions** (`-0.012` means `-1.2%`); probabilities range from 0 to 1. `relative_day` counts trading sessions and window endpoints are inclusive. Volume z-scores are standard-deviation units of log volume.

The `uncertainty` field distinguishes `predictive` (parameters plus future-return innovations) from `parameter_only` (conditional-mean parameter uncertainty). The post and main figures use `predictive`. CAR sums daily abnormal returns; it is not a compounded investment return.

[`outputs/posterior/`](../outputs/posterior/) contains one compressed NumPy `.npz` archive per event, with 4,000 draws, fitted parameters, predictive and parameter-only abnormal returns, CARs, dates, and JSON metadata. Inspect with `numpy.load(path, allow_pickle=False)`; `archive.files` lists the arrays. The full pipeline regenerates these files from the input snapshot.

The published result artifacts support inspection without running Python. They do not grant rights to underlying third-party market data. For the complete methodology and interpretation, see the [README](../README.md) and [results report](../report/results.md).
