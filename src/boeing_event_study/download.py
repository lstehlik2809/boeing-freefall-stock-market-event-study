"""Immutable pinned downloads, with a manifest verified before offline analysis."""
import hashlib
import io
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

import numpy as np
import pandas as pd

from .utils import load_config, make_directories, sha256, utc_now

FIELDS = ["ticker", "source_path", "source_commit", "source_url", "download_timestamp_utc",
          "rows", "min_date", "max_date", "file_size", "sha256"]


def parse_prices(content):
    frame = pd.read_csv(io.BytesIO(content))
    if not {"Date", "Close", "Volume"}.issubset(frame.columns):
        raise ValueError("Price CSV lacks Date, Close or Volume")
    # Trading dates are local exchange dates, not UTC-converted timestamps.
    frame["date"] = pd.to_datetime(frame.Date.astype(str).str[:10], format="%Y-%m-%d", errors="raise")
    if frame.empty or frame.date.duplicated().any() or not frame.date.is_monotonic_increasing:
        raise ValueError("Price dates must be nonempty, unique and sorted")
    frame["Close"] = pd.to_numeric(frame.Close, errors="raise")
    frame["Volume"] = pd.to_numeric(frame.Volume, errors="raise")
    if (~np.isfinite(frame.Close) | (frame.Close <= 0)).any():
        raise ValueError("Close must be finite and positive")
    return frame.set_index("date")


def source_url(cfg, path):
    return f"https://raw.githubusercontent.com/{cfg['source_repository']}/{cfg['source_commit']}/{quote(path, safe='/')}"


def metadata(ticker, path, cfg, content):
    frame = parse_prices(content)
    return dict(zip(FIELDS, [ticker, path, cfg["source_commit"], source_url(cfg, path), utc_now(), len(frame),
                            str(frame.index.min().date()), str(frame.index.max().date()), len(content),
                            hashlib.sha256(content).hexdigest()]))


def verify_snapshot(root, cfg=None):
    root = Path(root)
    cfg = cfg or load_config(root)[0]
    path = root / "data/data_manifest.csv"
    if not path.exists():
        raise ValueError("Frozen data manifest is missing; download a snapshot first")
    manifest = pd.read_csv(path)
    if not set(FIELDS).issubset(manifest.columns) or set(manifest.ticker) != set(cfg["source_paths"]) or manifest.ticker.duplicated().any():
        raise ValueError("Manifest does not describe exactly the configured source files")
    for record in manifest.to_dict("records"):
        ticker = record["ticker"]
        raw = root / f"data/raw/{ticker}.csv"
        if not raw.exists() or sha256(raw) != record["sha256"]:
            raise ValueError(f"Frozen raw file is missing or checksum differs: {ticker}; no data overwritten")
        actual = metadata(ticker, cfg["source_paths"][ticker], cfg, raw.read_bytes())
        for field in FIELDS:
            if field != "download_timestamp_utc" and str(actual[field]) != str(record[field]):
                raise ValueError(f"Manifest metadata mismatch: {ticker} {field}")
        pd.to_datetime(record["download_timestamp_utc"], errors="raise", utc=True)
    return manifest


def fetch_bytes(url):
    with urlopen(url, timeout=90) as response:
        return response.read()


def download(root, fetch=fetch_bytes):
    root = Path(root)
    cfg, _ = load_config(root)
    make_directories(root)
    manifest_path = root / "data/data_manifest.csv"
    existing_manifest = pd.read_csv(manifest_path) if manifest_path.exists() else None
    if existing_manifest is not None:
        # A manifest-only clone is supported; partial/tampered snapshots are not silently repaired.
        present = [(root / f"data/raw/{ticker}.csv").exists() for ticker in cfg["source_paths"]]
        if any(present):
            verify_snapshot(root, cfg)
    elif any((root / f"data/raw/{ticker}.csv").exists() for ticker in cfg["source_paths"]):
        raise ValueError("Raw files exist without their original manifest; refusing to overwrite")
    # Fetch/validate the entire batch before writing any raw data.
    payloads, records = {}, []
    for ticker, path in cfg["source_paths"].items():
        payloads[ticker] = fetch(source_url(cfg, path))
        records.append(metadata(ticker, path, cfg, payloads[ticker]))
    proposed = pd.DataFrame(records)
    if existing_manifest is not None:
        if set(existing_manifest.ticker) != set(proposed.ticker) or existing_manifest.ticker.duplicated().any():
            raise ValueError("Existing manifest has an invalid ticker set")
        old = existing_manifest.set_index("ticker")
        for record in records:
            for field in FIELDS:
                if field not in ("ticker", "download_timestamp_utc") and str(old.loc[record["ticker"], field]) != str(record[field]):
                    raise ValueError(f"Source changed: {record['ticker']} {field}; frozen data NOT overwritten")
    for ticker, content in payloads.items():
        path = root / f"data/raw/{ticker}.csv"
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(content)
    if existing_manifest is None:
        proposed.to_csv(manifest_path, index=False)
    return verify_snapshot(root, cfg)
