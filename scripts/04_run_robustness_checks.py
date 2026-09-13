from pathlib import Path
from boeing_event_study.frequentist import run_robustness

if __name__ == "__main__":
    run_robustness(Path(__file__).resolve().parents[1])
