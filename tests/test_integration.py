"""AS-v1 full numerical output checks. Missing artifacts fail, never skip.

Run scripts/run_all.py before pytest. Runtime reproduction is an explicit prerequisite.
"""
import json
from pathlib import Path
import runpy
import shutil
import socket
import sys

import numpy as np
import pandas as pd
import pytest

from boeing_event_study.download import verify_snapshot
from boeing_event_study.replication import apply_reviewed_resolution, replication_table
from boeing_event_study.utils import load_config, read_panel, relative_slice, sha256, validate_contamination

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.integration


def test_every_brief_replication_target_in_single_table():
    diagnostics = apply_reviewed_resolution(ROOT, replication_table(ROOT))
    assert len(diagnostics) == 52
    assert diagnostics.passed.sum() == 51
    assert diagnostics.reviewed.sum() == 1
    assert (diagnostics.passed | diagnostics.reviewed).all()
    row = diagnostics.loc[diagnostics.reviewed].iloc[0]
    assert not row.passed and row.status == "reviewed_reference_difference"
    assert (row.event, row.window, row.metric) == ("netflix", "[0,+10]", "median")
    saved = pd.read_csv(ROOT / "outputs/tables/replication_diagnostics.csv")
    pd.testing.assert_frame_equal(saved, diagnostics, check_dtype=False, atol=1e-14)


def test_full_snapshot_calendar_and_event_outputs():
    cfg, events = load_config(ROOT)
    manifest = verify_snapshot(ROOT, cfg)
    assert len(manifest) == 8 and manifest.max_date.eq("2026-09-11").all()
    validate_contamination(ROOT, events)
    panel = read_panel(ROOT)
    summary = pd.read_csv(ROOT / "outputs/tables/bayesian_event_windows.csv")
    assert len(summary) == 40
    for event in events:
        estimation = relative_slice(panel, event["date"], -250, -30, required=["ba_return", "market_return", "sector_return"])
        assert len(estimation) == 221
        with np.load(ROOT / f"outputs/posterior/{event['id']}.npz") as draws:
            assert draws["beta"].shape == (4000, 3)
            assert draws["sigma2"].shape == (4000,)
            assert draws["ar_predictive"].shape == (4000, 16)
            assert draws["ar_parameter_only"].shape == (4000, 16)
            assert draws["car_predictive"].shape == (4000, 5)
            meta = json.loads(str(draws["metadata_json"]))
            assert meta["seed"] == 20260912 and meta["estimation_n"] == 221
            np.testing.assert_allclose(draws["ar_predictive"], draws["observed_return"][None, :] - draws["counterfactual"])
            np.testing.assert_allclose(draws["ar_parameter_only"], draws["observed_return"][None, :] - draws["mu"])
            assert np.var(draws["car_predictive"][:, 0]) > 5 * np.var(draws["car_parameter_only"][:, 0])
            for j, (start, end) in enumerate(cfg["windows"].values()):
                offsets = draws["relative_days"]
                expected = draws["ar_predictive"][:, (offsets >= start) & (offsets <= end)].sum(axis=1)
                np.testing.assert_allclose(draws["car_predictive"][:, j], expected)


def test_robustness_volume_figures_and_provenance_complete():
    ols = pd.read_csv(ROOT / "outputs/tables/frequentist_event_windows.csv")
    placebos = pd.read_csv(ROOT / "outputs/tables/placebo_results.csv")
    volume = pd.read_csv(ROOT / "outputs/tables/volume_event_study.csv")
    assert len(ols) == len(placebos) == 40
    assert set(ols.specification) == {"market_only", "market_sector"}
    np.testing.assert_array_equal(placebos.n_placebos, 222 - placebos.n_days)
    assert placebos[["p_lower", "p_two_sided"]].gt(0).all().all()
    assert placebos[["p_lower", "p_two_sided"]].le(1).all().all()
    assert len(volume) == 64
    assert volume.groupby("event").relative_day.apply(list).tolist() == [list(range(-5, 11))] * 4
    for stem in ("comparative_car", "event_window_forest", "abnormal_volume", "supplement_sampler_traces"):
        for suffix in ("png", "svg"):
            assert (ROOT / f"outputs/figures/{stem}.{suffix}").stat().st_size > 10_000
    provenance = json.loads((ROOT / "outputs/logs/reproducibility.json").read_text())
    assert provenance["random_seed"] == 20260912
    assert provenance["python_version"] and provenance["platform"] and provenance["packages"]
    assert len(provenance["raw_sha256"]) == 8
    for path, checksum in provenance["project_sha256"].items():
        assert sha256(ROOT / path) == checksum, f"Re-run pipeline after changing {path}"


def test_offline_full_rerun_has_no_network_and_identical_numerics(monkeypatch):
    raw_paths = list((ROOT / "data/raw").glob("*.csv")) + [ROOT / "data/data_manifest.csv"]
    raw_before = {path: sha256(path) for path in raw_paths}
    table_paths = list((ROOT / "outputs/tables").glob("*.csv"))
    tables_before = {path: path.read_bytes() for path in table_paths}
    posterior_before = {}
    for path in (ROOT / "outputs/posterior").glob("*.npz"):
        with np.load(path) as draws:
            posterior_before[path] = {key: draws[key].copy() for key in draws.files}

    def forbidden_network(*args, **kwargs):
        raise AssertionError("Offline reproduction attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(sys, "argv", [str(ROOT / "scripts/run_all.py"), "--skip-download"])
    runpy.run_path(str(ROOT / "scripts/run_all.py"), run_name="__main__")
    assert {path: sha256(path) for path in raw_paths} == raw_before
    assert {path: path.read_bytes() for path in table_paths} == tables_before
    for path, arrays in posterior_before.items():
        with np.load(path) as after:
            for key, expected in arrays.items():
                np.testing.assert_array_equal(after[key], expected, err_msg=f"Changed offline posterior {path.name}/{key}")


def test_clean_output_reproduction_from_frozen_inputs(tmp_path, monkeypatch):
    """No generated output/report is supplied; rebuilding must have no hidden artifact prerequisites."""
    for directory in ("config", "scripts", "src", "data/raw", "report/sources"):
        shutil.copytree(ROOT / directory, tmp_path / directory, ignore=shutil.ignore_patterns("__pycache__"))
    for relative in ("data/data_manifest.csv", "pyproject.toml", "uv.lock", ".python-version", ".gitattributes",
                     "README.md", "LICENSE", "CITATION.cff", "report.py"):
        shutil.copyfile(ROOT / relative, tmp_path / relative)
    assert not (tmp_path / "outputs").exists()

    def forbidden_network(*args, **kwargs):
        raise AssertionError("Clean offline reproduction attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "scripts/run_all.py"), "--skip-download"])
    runpy.run_path(str(tmp_path / "scripts/run_all.py"), run_name="__main__")
    for expected in (ROOT / "outputs/tables").glob("*.csv"):
        assert (tmp_path / "outputs/tables" / expected.name).read_bytes() == expected.read_bytes()
    for relative in ("outputs/logs/netflix_predictive_mc_diagnostic.json", "outputs/logs/reproducibility.json",
                     "outputs/figures/comparative_car.png", "report/results.md"):
        assert (tmp_path / relative).stat().st_size > 100
    for expected in (ROOT / "outputs/posterior").glob("*.npz"):
        with np.load(expected) as before, np.load(tmp_path / "outputs/posterior" / expected.name) as after:
            for key in before.files:
                np.testing.assert_array_equal(before[key], after[key])
