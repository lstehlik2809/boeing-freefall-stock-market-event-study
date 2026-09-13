"""Bounded diagnostic of the failed Netflix +10 target; never replaces production draws."""
import json
from pathlib import Path

from boeing_event_study.replication import write_mc_diagnostic


def main():
    root = Path(__file__).resolve().parents[1]
    output = write_mc_diagnostic(root)
    print(json.dumps({k: v for k, v in output.items() if k != "replicate_medians"}, indent=2))


if __name__ == "__main__":
    main()
