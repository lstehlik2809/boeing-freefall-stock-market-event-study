# Source verification

Research date: 2026-09-12. These are source notes, not an independent audit of the data vendor.

## Market-data snapshot

- Repository: [zjplab/US-Trading-Data](https://github.com/zjplab/US-Trading-Data).
- Frozen revision: `14fec12f4af23d69633b6fd37e6d477facf0fa2b`.
- The [README at that revision](https://github.com/zjplab/US-Trading-Data/blob/14fec12f4af23d69633b6fd37e6d477facf0fa2b/README.md) identifies Yahoo Finance through yfinance as the source and reports an update at 2026-09-12 02:49:24 UTC.
- The [upstream downloader](https://github.com/zjplab/US-Trading-Data/blob/14fec12f4af23d69633b6fd37e6d477facf0fa2b/update_stock_data.py) calls `Ticker.history(period="max", interval="1d")` without overriding price adjustment. The supplied `Close` values are used exactly as requested; they must not be described as independently verified unadjusted exchange closes. No second dividend/split adjustment is applied. The upstream package version and historical vendor revisions are not recoverable from these CSVs alone.
- The local manifest records the exact bytes, paths, timestamps and observed coverage for all eight downloaded files. A pinned Git revision reduces changes from the daily upstream refresh; it does not guarantee permanent upstream availability.

## Redistribution assessment

The repository declares [GPL-3.0](https://github.com/zjplab/US-Trading-Data/blob/14fec12f4af23d69633b6fd37e6d477facf0fa2b/LICENSE). This declaration alone does not establish rights to redistribute Yahoo-derived market prices. The [yfinance project](https://github.com/ranaroussi/yfinance/blob/main/README.md) directs users to Yahoo's terms for rights to downloaded data and describes the API as intended for personal use.

Accordingly, redistribution permission has **not been established**. Raw and processed market CSVs remain local and are excluded by `.gitignore`. The published code, frozen source paths, manifest and SHA-256 hashes provide reconstruction without including those CSVs in the public repository. The project's software license does not license third-party market data or source articles. The upstream README and yfinance notice were checked again during repository preparation on 2026-09-13; the redistribution conclusion remains unchanged.

## Documentary identity and dates

- [Netflix Media Center](https://media.netflix.com/en/only-on-netflix/81780118) confirms the film's identity, filmmakers and relationship to *Downfall* (2022).
- [Rotten Tomatoes release metadata](https://www.rottentomatoes.com/m/freefall_a_reckoning_for_boeing) lists limited theatrical release on **2026-08-14** and streaming release on **2026-08-19**. These are the sensitivity and primary dates respectively.
- Netflix's description refers to new revelations. We therefore do not establish or assume that everything in the film was previously public. How much information was new to investors is an identification uncertainty, not a measured result of this stock-return study.

Event-specific news sources and research coverage are recorded separately in `config/event_contamination.csv` and `report/sources/contamination_research.md`.
