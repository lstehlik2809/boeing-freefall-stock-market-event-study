"""AS12 diagnosis resolution is narrow and never converts a tolerance failure into a pass."""
from pathlib import Path
import shutil

import numpy as np
import pytest
import yaml

import boeing_event_study.replication as replication

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def reviewed_root(tmp_path):
    resolution = yaml.safe_load((ROOT / "config/replication_resolutions.yml").read_text())
    paths = list(resolution["bound_file_sha256"]) + ["config/replication_resolutions.yml", "outputs/posterior/netflix.npz"]
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    (tmp_path / "outputs/tables").mkdir()
    return tmp_path


def test_reviewed_difference_retains_false_and_exact_scope(reviewed_root):
    raw = replication.replication_table(ROOT)
    resolved = replication.apply_reviewed_resolution(reviewed_root, raw)
    assert resolved.passed.sum() == 51
    assert resolved.reviewed.sum() == 1
    failed = resolved.loc[~resolved.passed].iloc[0]
    assert failed.status == "reviewed_reference_difference"
    assert failed.tolerance == .0035
    assert failed.absolute_difference > failed.tolerance


@pytest.mark.parametrize("mutation", ["actual", "target", "tolerance", "configuration", "source", "diagnostic", "lockfile", "dependencies"])
def test_resolution_rejects_changed_bound_inputs(reviewed_root, mutation):
    table = replication.replication_table(ROOT)
    mask = (table.event == "netflix") & (table.window == "[0,+10]") & (table.metric == "median")
    if mutation in ("actual", "target", "tolerance"):
        table.loc[mask, mutation] += .000001
    else:
        relative = {"configuration": "config/analysis.yml", "source": "src/boeing_event_study/bayes.py",
                    "diagnostic": "config/replication_review_evidence.json",
                    "lockfile": "uv.lock", "dependencies": "pyproject.toml"}[mutation]
        path = reviewed_root / relative
        path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="stale evidence|no longer matches"):
        replication.apply_reviewed_resolution(reviewed_root, table)


def test_posterior_byte_difference_visible_without_blocking_same_numeric_target(reviewed_root):
    path = reviewed_root / "outputs/posterior/netflix.npz"
    with np.load(path) as archive:
        arrays = {key: archive[key] for key in archive.files}
    arrays["beta"][0, 0] = np.nextafter(arrays["beta"][0, 0], np.inf)
    np.savez_compressed(path, **arrays)
    result = replication.apply_reviewed_resolution(reviewed_root, replication.replication_table(ROOT))
    row = result.loc[result.reviewed].iloc[0]
    assert not row.passed
    assert row.posterior_fingerprint_audit == "mismatch"


@pytest.mark.parametrize("origin", ["observed", "expected"])
@pytest.mark.parametrize("metric", ["actual", "target", "tolerance"])
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")], ids=["nan", "positive_inf", "negative_inf"])
def test_resolution_rejects_nonfinite_numeric_values(reviewed_root, origin, metric, invalid):
    table = replication.replication_table(ROOT)
    mask = (table.event == "netflix") & (table.window == "[0,+10]") & (table.metric == "median")
    if origin == "observed":
        table.loc[mask, metric] = invalid
    else:
        path = reviewed_root / "config/replication_resolutions.yml"
        resolution = yaml.safe_load(path.read_text())
        resolution["reviewed_check"][metric] = invalid
        path.write_text(yaml.safe_dump(resolution, sort_keys=False))
    with pytest.raises(ValueError, match=f"requires finite {origin} {metric}"):
        replication.apply_reviewed_resolution(reviewed_root, table)


def test_new_unrelated_mismatch_still_stops_gate(reviewed_root, monkeypatch):
    table = replication.replication_table(ROOT)
    table.loc[0, ["actual", "absolute_difference", "passed"]] = [-.5, .4071, False]
    monkeypatch.setattr(replication, "replication_table", lambda root: table)
    with pytest.raises(ValueError, match="stop and diagnose"):
        replication.check_replication(reviewed_root)


def test_missing_resolution_never_waives_failed_check(tmp_path, monkeypatch):
    (tmp_path / "outputs/tables").mkdir(parents=True)
    table = replication.replication_table(ROOT)
    monkeypatch.setattr(replication, "replication_table", lambda root: table)
    with pytest.raises(ValueError, match="stop and diagnose"):
        replication.check_replication(tmp_path)
