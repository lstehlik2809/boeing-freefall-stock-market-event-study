"""Fixed, pre-run diagnostic tolerances for every numerical target in brief §12."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import yaml

from .utils import sha256, utc_now

TOLERANCES = {"median": .0035, "ci95_low": .0075, "ci95_high": .0075,
              "probability": .04, "volume_z": .15}

# Decimal returns, not percentages. Targets and tolerances must not be fitted to results.
WINDOW_TARGETS = {
    ("alaska", "[0,0]"): dict(median=-.0929, ci95_low=-.1202, ci95_high=-.0656, p_lt_0=1.000),
    ("alaska", "[-1,+1]"): dict(median=-.0885, ci95_low=-.1372, ci95_high=-.0424, p_lt_0=.999),
    ("alaska", "[0,+5]"): dict(median=-.2220, ci95_low=-.2878, ci95_high=-.1527),
    ("hearing", "[0,0]"): dict(median=-.0217, ci95_low=-.0536, ci95_high=.0116, p_lt_0=.922),
    ("hearing", "[-1,+1]"): dict(median=-.0151, ci95_low=-.0734, ci95_high=.0432, p_lt_0=.720),
    ("hearing", "[0,+5]"): dict(median=.0126),
    ("netflix", "[0,0]"): dict(median=.0059, ci95_low=-.0281, ci95_high=.0387, p_lt_0=.339),
    ("netflix", "[-1,+1]"): dict(median=-.0132, ci95_low=-.0720, ci95_high=.0455, p_lt_0=.699),
    ("netflix", "[0,+5]"): dict(median=-.0079, ci95_low=-.0909, ci95_high=.0767, p_lt_0=.584),
    ("netflix", "[0,+10]"): dict(median=.0141),
    ("theatrical", "[0,0]"): dict(median=.0007),
    ("theatrical", "[-1,+1]"): dict(median=-.0161),
    ("theatrical", "[-3,+3]"): dict(median=-.0282),
    ("theatrical", "[0,+5]"): dict(median=-.0271),
    ("theatrical", "[0,+10]"): dict(median=-.0401),
}
COMPARISON_TARGETS = {
    "[-1,+1]": dict(p_alaska_lt_hearing=.973, p_hearing_lt_netflix=.524, p_alaska_lt_netflix=.975),
    "[0,+5]": dict(p_alaska_lt_hearing=1.000, p_hearing_lt_netflix=.358, p_alaska_lt_netflix=1.000),
}
VOLUME_TARGETS = {"alaska": 5.50, "hearing": .02, "netflix": -.48}


def replication_table(root):
    tables = Path(root) / "outputs/tables"
    bayesian = pd.read_csv(tables / "bayesian_event_windows.csv").query("uncertainty == 'predictive'").set_index(["event", "window"])
    comparisons = pd.read_csv(tables / "comparisons.csv").query("uncertainty == 'predictive'").set_index("window")
    volume = pd.read_csv(tables / "volume_event_study.csv").query("relative_day == 0").set_index("event")
    rows = []

    def append(group, event, window, metric, target, actual, tolerance):
        rows.append({"group": group, "event": event, "window": window, "metric": metric,
                     "target": target, "actual": actual, "absolute_difference": abs(actual - target),
                     "tolerance": tolerance, "passed": abs(actual - target) <= tolerance})

    for (event, window), targets in WINDOW_TARGETS.items():
        for metric, target in targets.items():
            tolerance = TOLERANCES["probability"] if metric.startswith("p_") else TOLERANCES[metric]
            append("bayesian", event, window, metric, target, bayesian.loc[(event, window), metric], tolerance)
    for window, targets in COMPARISON_TARGETS.items():
        for metric, target in targets.items():
            append("comparison", "three_primary_events", window, metric, target, comparisons.loc[window, metric], .04)
    for event, target in VOLUME_TARGETS.items():
        append("volume", event, "[0,0]", "volume_z", target, volume.loc[event, "volume_z"], .15)
    for window in (label for event, label in WINDOW_TARGETS if event == "theatrical"):
        row = bayesian.loc[("theatrical", window)]
        append("theatrical_interval", "theatrical", window, "ci95_contains_zero", 1,
               int(row.ci95_low < 0 < row.ci95_high), 0)
    return pd.DataFrame(rows)


def posterior_fingerprint(path):
    """Hash semantic numeric arrays, independent of ZIP timestamps/compression metadata."""
    digest = hashlib.sha256()
    with np.load(path) as draws:
        for key in ("beta", "sigma2", "ar_predictive"):
            array = np.ascontiguousarray(draws[key])
            digest.update(key.encode())
            digest.update(str(array.shape).encode())
            digest.update(array.dtype.str.encode())
            digest.update(array.tobytes())
    return digest.hexdigest()


def write_mc_diagnostic(root):
    """Regenerate current bounded predictive diagnostics; archived review evidence lives in config."""
    from .bayes import predictive_errors

    root = Path(root)
    path = root / "outputs/posterior/netflix.npz"
    with np.load(path) as draws:
        index = list(draws["window_labels"]).index("[0,+10]")
        center = draws["car_parameter_only"][:, index]
        observed = np.median(draws["car_predictive"][:, index])
        sigma2 = draws["sigma2"]
    seeds = np.random.SeedSequence([20260912, 999]).spawn(32)
    replicates = [center - predictive_errors(sigma2, 11, 5, np.random.default_rng(seed)).sum(axis=1) for seed in seeds]
    medians = np.array([np.median(values) for values in replicates])
    output = {
        "timestamp_utc": utc_now(), "production_posterior_semantic_sha256": posterior_fingerprint(path),
        "purpose": "Current diagnostic only; immutable original review evidence is config/replication_review_evidence.json",
        "diagnostic_seed_entropy": [20260912, 999], "independent_predictive_replicates": 32,
        "draws_per_replicate": 4000, "target": .0141, "production_median": float(observed),
        "parameter_only_mean": float(center.mean()), "parameter_only_median": float(np.median(center)),
        "replicate_medians": medians.tolist(), "replicate_median_mean": float(medians.mean()),
        "replicate_median_sd": float(medians.std(ddof=1)),
        "replicate_median_range": [float(medians.min()), float(medians.max())],
        "replicate_median_95pct_range": np.quantile(medians, [.025, .975]).tolist(),
        "pooled_128000_predictive_median": float(np.median(np.concatenate(replicates))),
        "target_distance_in_replicate_sd": float((.0141 - medians.mean()) / medians.std(ddof=1)),
        "production_distance_in_replicate_sd": float((observed - medians.mean()) / medians.std(ddof=1)),
        "limitations": "Original implementation and RNG stream are unavailable; Monte Carlo plausibility is not proof of exact cause. Conditional fresh-noise replications exclude uncertainty from rerunning coefficient chains.",
    }
    (root / "outputs/logs/netflix_predictive_mc_diagnostic.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def apply_reviewed_resolution(root, result):
    """Preserve failed tolerances; recognize only the exact independently reviewed artifact."""
    root = Path(root)
    result = result.copy()
    result["reviewed"] = False
    result["status"] = np.where(result.passed, "within_tolerance", "unresolved_reference_difference")
    result["posterior_fingerprint_audit"] = "not_applicable"
    path = root / "config/replication_resolutions.yml"
    if not path.exists() or result.passed.all():
        return result
    resolution = yaml.safe_load(path.read_text(encoding="utf-8"))
    # There is deliberately no generic ignore-failure or relaxed-tolerance switch.
    if resolution["id"] != "AS12-NETFLIX10-1":
        raise ValueError("Unknown replication resolution")
    for relative, expected_hash in resolution["bound_file_sha256"].items():
        candidate = root / relative
        if not candidate.is_file() or sha256(candidate) != expected_hash:
            raise ValueError(f"Reviewed reference difference has stale evidence/config/source: {relative}")
    # Byte fingerprints are audit evidence, not a portable numerical equality test:
    # equivalent BLAS/Python runtimes may differ in insignificant floating-point bits.
    fingerprint_matches = (posterior_fingerprint(root / "outputs/posterior/netflix.npz")
                           == resolution["posterior_semantic_sha256"])
    match = ((result.group == "bayesian") & (result.event == "netflix") & (result.window == "[0,+10]")
             & (result.metric == "median") & ~result.passed)
    if match.sum() != 1:
        return result
    row = result.loc[match].iloc[0]
    expected = resolution["reviewed_check"]
    for origin, values in (("observed", row), ("expected", expected)):
        for metric in ("actual", "target", "tolerance"):
            if not np.isfinite(values[metric]):
                raise ValueError(f"Reviewed reference difference requires finite {origin} {metric}")
    if (expected["event"] != "netflix" or expected["window"] != "[0,+10]" or expected["metric"] != "median"
            or abs(row.target - expected["target"]) > 1e-12
            or abs(row.actual - expected["actual"]) > 1e-12
            or row.tolerance != expected["tolerance"]):
        raise ValueError("Reviewed reference difference no longer matches the reviewed numerical check")
    result.loc[match, "reviewed"] = True
    result.loc[match, "status"] = "reviewed_reference_difference"
    result.loc[match, "posterior_fingerprint_audit"] = "match" if fingerprint_matches else "mismatch"
    return result


def check_replication(root):
    result = apply_reviewed_resolution(root, replication_table(root))
    result.to_csv(Path(root) / "outputs/tables/replication_diagnostics.csv", index=False)
    failures = result.loc[~result.passed & ~result.reviewed]
    if len(failures):
        raise ValueError("Material replication differences; stop and diagnose without tuning tolerances:\n" + failures.to_string(index=False))
    print(f"Replication diagnostics: {result.passed.sum()}/{len(result)} within tolerance; "
          f"{result.reviewed.sum()} reviewed reference difference(s)", flush=True)
    if result.reviewed.any():
        print("WARNING: Netflix [0,+10] median remains outside its original tolerance. The preserved "
              "difference was reviewed; its exact cause is unestablished. See config/replication_resolutions.yml.", flush=True)
        if result.loc[result.reviewed, "posterior_fingerprint_audit"].eq("mismatch").any():
            print("AUDIT: posterior array bytes differ from the reviewed artifact; bound source/config/data "
                  "and target checks still match within 1e-12.", flush=True)
    return result
