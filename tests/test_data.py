"""AS-v1: independent hand fixtures for snapshot integrity and trading-calendar returns."""
import hashlib
import numpy as np
import pandas as pd
import pytest
import yaml

from boeing_event_study.download import download, parse_prices, verify_snapshot
from boeing_event_study.prepare import construct_panel, simple_returns
from boeing_event_study.utils import relative_slice, validate_contamination


CSV = b"Date,Close,Volume\n2024-01-02 00:00:00-05:00,100,1000\n2024-01-03 00:00:00-05:00,110,1200\n"


@pytest.fixture
def snapshot_root(tmp_path):
    (tmp_path / "config").mkdir()
    cfg = {"source_repository": "fixture/repo", "source_commit": "a" * 40,
           "source_paths": {"BA": "data/SP500/BA.csv", "GSPC": "data/Indexes/^GSPC.csv"}}
    (tmp_path / "config/analysis.yml").write_text(yaml.safe_dump(cfg))
    (tmp_path / "config/events.yml").write_text("events: []")
    return tmp_path


def test_download_metadata_and_identical_redownload(snapshot_root):
    root = snapshot_root
    result = download(root, fetch=lambda url: CSV)
    assert result.rows.tolist() == [2, 2]
    assert result.min_date.tolist() == ["2024-01-02"] * 2
    assert result.max_date.tolist() == ["2024-01-03"] * 2
    assert result.file_size.tolist() == [len(CSV)] * 2
    assert result.sha256.tolist() == [hashlib.sha256(CSV).hexdigest()] * 2
    assert result.source_url.str.contains("a" * 40).all()
    assert result.source_url.str.startswith("https://raw.githubusercontent.com/fixture/repo/").all()
    assert pd.to_datetime(result.download_timestamp_utc, utc=True).notna().all()
    before = (root / "data/data_manifest.csv").read_bytes()
    download(root, fetch=lambda url: CSV)
    assert (root / "data/data_manifest.csv").read_bytes() == before
    assert (root / "data/raw/BA.csv").read_bytes() == CSV


def test_changed_source_refused_without_writes(snapshot_root):
    download(snapshot_root, fetch=lambda url: CSV)
    before = {p: p.read_bytes() for p in (snapshot_root / "data").rglob("*.csv")}
    with pytest.raises(ValueError, match="Source changed"):
        download(snapshot_root, fetch=lambda url: CSV.replace(b"110", b"111"))
    assert all(path.read_bytes() == content for path, content in before.items())


def test_failed_batch_does_not_create_partial_raw_files(snapshot_root):
    def fetch(url):
        if "Indexes" in url:
            raise OSError("simulated connection failure")
        return CSV
    with pytest.raises(OSError, match="connection failure"):
        download(snapshot_root, fetch=fetch)
    assert list((snapshot_root / "data/raw").glob("*.csv")) == []
    assert not (snapshot_root / "data/data_manifest.csv").exists()


def test_offline_missing_or_tampered_fails(snapshot_root):
    with pytest.raises(ValueError, match="manifest is missing"):
        verify_snapshot(snapshot_root)
    download(snapshot_root, fetch=lambda url: CSV)
    (snapshot_root / "data/raw/BA.csv").write_bytes(CSV + b"\n")
    with pytest.raises(ValueError, match="checksum differs"):
        verify_snapshot(snapshot_root)
    with pytest.raises(ValueError, match="checksum differs"):
        download(snapshot_root, fetch=lambda url: pytest.fail("must verify before fetching"))
    (snapshot_root / "data/raw/BA.csv").unlink()
    with pytest.raises(ValueError, match="missing or checksum"):
        verify_snapshot(snapshot_root)


def test_manifest_only_clone_reconstructs_frozen_snapshot(snapshot_root):
    original = download(snapshot_root, fetch=lambda url: CSV)
    for path in (snapshot_root / "data/raw").glob("*.csv"):
        path.unlink()
    result = download(snapshot_root, fetch=lambda url: CSV)
    pd.testing.assert_frame_equal(result, original)


def test_invalid_dates_prices_and_manifest_metadata(snapshot_root):
    with pytest.raises(ValueError, match="unique"):
        parse_prices(CSV + b"2024-01-03,120,1300\n")
    with pytest.raises(ValueError, match="positive"):
        parse_prices(CSV.replace(b",110,", b",0,"))
    download(snapshot_root, fetch=lambda url: CSV)
    path = snapshot_root / "data/data_manifest.csv"
    manifest = pd.read_csv(path)
    manifest.loc[0, "rows"] = 999
    manifest.to_csv(path, index=False)
    with pytest.raises(ValueError, match="metadata mismatch"):
        verify_snapshot(snapshot_root)


def test_simple_daily_returns_are_not_logs_and_never_fill():
    actual = simple_returns(pd.Series([100., 110., np.nan, 121., 110.]))
    np.testing.assert_allclose(actual, [np.nan, .1, np.nan, np.nan, -1/11], equal_nan=True)


def test_alignment_reindexes_before_returns_and_peer_five_boundary():
    dates = pd.bdate_range("2024-01-02", periods=5)
    prices = {name: pd.DataFrame({"Close": [100, 110, 121, 133.1, 146.41], "Volume": [10]*5}, index=dates)
              for name in ["BA", "GSPC", "P1", "P2", "P3", "P4", "P5", "P6"]}
    prices["BA"] = prices["BA"].drop(dates[2])
    prices["P6"] = prices["P6"].drop(dates[1])
    prices["P5"] = prices["P5"].drop(dates[2])
    panel = construct_panel(prices, [f"P{i}" for i in range(1, 7)])
    assert panel.index.equals(dates)
    assert np.isnan(panel.loc[dates[2], "ba_return"])
    assert np.isnan(panel.loc[dates[3], "ba_return"])
    assert panel.loc[dates[1], "peer_count"] == 5
    assert panel.loc[dates[1], "peer_return"] == pytest.approx(.1)
    assert panel.loc[dates[2], "peer_count"] == 4
    assert np.isnan(panel.loc[dates[2], "peer_return"])
    assert panel.loc[dates[3], "sector_return"] == pytest.approx(0)


def test_trading_calendar_holiday_window_length_and_missing_required():
    dates = pd.bdate_range("2023-01-01", "2024-03-01").difference(pd.to_datetime(["2024-01-01", "2024-01-15"]))
    panel = pd.DataFrame({"value": np.arange(len(dates), dtype=float)}, index=dates)
    estimation = relative_slice(panel, "2024-01-08", -250, -30, required=["value"])
    assert len(estimation) == 221
    assert estimation.relative_day.iloc[[0, -1]].tolist() == [-250, -30]
    assert relative_slice(panel, "2024-01-02", -1, -1).index[0] == pd.Timestamp("2023-12-29")
    for start, end, length in [(0, 0, 1), (-1, 1, 3), (-3, 3, 7), (0, 5, 6), (0, 10, 11)]:
        assert len(relative_slice(panel, "2024-01-08", start, end)) == length
    with pytest.raises(ValueError, match="not in the market"):
        relative_slice(panel, "2024-01-01", 0, 1)
    panel.loc["2024-01-05", "value"] = np.nan
    with pytest.raises(ValueError, match="Missing"):
        relative_slice(panel, "2024-01-08", -1, 1, required=["value"])
    with pytest.raises(ValueError, match="Insufficient"):
        relative_slice(panel, "2023-01-02", -1, 1)


def test_contamination_log_mandatory(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        validate_contamination(tmp_path, [{"id": "alaska"}])
    (tmp_path / "config").mkdir()
    pd.DataFrame([{"date": "2024-01-08", "event": "hearing", "potentially_confounding_news": "news", "source": "https://example.com", "severity": "high", "notes": "context"}]).to_csv(tmp_path / "config/event_contamination.csv", index=False)
    with pytest.raises(ValueError, match="every configured event"):
        validate_contamination(tmp_path, [{"id": "alaska"}])
