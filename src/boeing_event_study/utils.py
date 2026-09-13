"""Configuration, strict trading-calendar selection and provenance."""
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_config(root):
    root = Path(root)
    cfg = yaml.safe_load((root / "config/analysis.yml").read_text(encoding="utf-8"))
    events = yaml.safe_load((root / "config/events.yml").read_text(encoding="utf-8"))["events"]
    return cfg, events


def make_directories(root):
    for name in ("data/raw", "data/processed", "outputs/tables", "outputs/figures", "outputs/posterior", "outputs/logs"):
        (Path(root) / name).mkdir(parents=True, exist_ok=True)


def relative_slice(panel, event_date, start, end, required=()):
    """Select offsets on the intact market calendar, never on complete-case rows."""
    date = pd.Timestamp(event_date)
    if not panel.index.is_unique or not panel.index.is_monotonic_increasing:
        raise ValueError("Trading calendar must be sorted and unique")
    if date not in panel.index:
        raise ValueError(f"Event date {date.date()} is not in the market trading calendar")
    loc = panel.index.get_loc(date)
    if start > end or loc + start < 0 or loc + end >= len(panel):
        raise ValueError(f"Insufficient calendar coverage for {event_date}: [{start},{end}]")
    result = panel.iloc[loc + start:loc + end + 1].copy()
    result["relative_day"] = np.arange(start, end + 1)
    if required and not np.isfinite(result[list(required)].to_numpy(dtype=float)).all():
        raise ValueError(f"Missing or nonfinite required data for {event_date}: [{start},{end}]")
    return result


def design_matrix(frame, market_only=False):
    cols = ["market_return"] if market_only else ["market_return", "sector_return"]
    return np.column_stack([np.ones(len(frame)), frame[cols].to_numpy()])


def read_panel(root):
    return pd.read_csv(Path(root) / "data/processed/daily_returns.csv", parse_dates=["date"]).set_index("date")


def validate_contamination(root, events):
    path = Path(root) / "config/event_contamination.csv"
    if not path.exists():
        raise ValueError("Mandatory event contamination log is missing")
    frame = pd.read_csv(path, keep_default_na=False)
    required = ["date", "event", "potentially_confounding_news", "source", "severity", "notes"]
    if not set(required).issubset(frame.columns) or frame.empty:
        raise ValueError("Contamination log must contain all six required columns and research entries")
    if frame[required].eq("").any().any():
        raise ValueError("Contamination log contains blank required fields")
    pd.to_datetime(frame.date, errors="raise")
    if not {event["id"] for event in events}.issubset(set(frame.event)):
        raise ValueError("Contamination log must cover every configured event ID")
    if not frame.source.str.match(r"https?://").all():
        raise ValueError("Contamination log sources must be reviewable HTTP(S) URLs")
    return frame


def write_provenance(root, cfg, manifest):
    root = Path(root)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    git_status = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True)
    source_files = sorted(p for folder in ("src", "scripts", "config", "tests")
                          for p in (root / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    source_files += [root / name for name in ("pyproject.toml", "uv.lock", ".python-version", ".gitattributes",
                                             "report.py", "README.md", "LICENSE", "CITATION.cff")]
    source_files += sorted((root / "report/sources").glob("*.md"))
    info = {
        "analysis_timestamp_utc": utc_now(), "python_version": sys.version,
        "platform": platform.platform(), "random_seed": cfg["seed"],
        "git_commit": git.stdout.strip() if git.returncode == 0 else None,
        "git_status": git_status.stdout.strip() if git_status.returncode == 0 else "not a Git repository",
        "packages": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scipy", "matplotlib", "PyYAML", "boeing-event-study")},
        "source_commit": cfg["source_commit"], "raw_sha256": dict(zip(manifest.ticker, manifest.sha256)),
        "project_sha256": {p.relative_to(root).as_posix(): sha256(p) for p in source_files if p.exists()},
        "analysis_config": cfg,
        "return_convention": "simple Close returns; source history auto-adjusted Close used without further adjustment",
    }
    (root / "outputs/logs/reproducibility.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
