"""Authoritative reproduction entry point. No network calls after data acquisition."""
import argparse
import importlib.util
from pathlib import Path

from boeing_event_study.bayes import run_bayesian
from boeing_event_study.download import download, verify_snapshot
from boeing_event_study.frequentist import run_robustness
from boeing_event_study.plotting import make_figures
from boeing_event_study.prepare import prepare
from boeing_event_study.replication import check_replication, write_mc_diagnostic
from boeing_event_study.utils import load_config, make_directories, validate_contamination, write_provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-download", action="store_true", help="Use and verify the frozen local snapshot; no network")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cfg, events = load_config(root)
    make_directories(root)
    validate_contamination(root, events)
    manifest = verify_snapshot(root, cfg) if args.skip_download else download(root)
    prepare(root)
    run_bayesian(root)
    run_robustness(root)
    write_mc_diagnostic(root)
    write_provenance(root, cfg, manifest)
    check_replication(root)
    make_figures(root)
    report_path = root / "report.py"
    if report_path.exists():
        spec = importlib.util.spec_from_file_location("event_study_report", report_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.generate_report(root)
    print("Full local reproduction complete", flush=True)


if __name__ == "__main__":
    main()
