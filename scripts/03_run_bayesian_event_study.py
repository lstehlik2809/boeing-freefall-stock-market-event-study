from pathlib import Path
from boeing_event_study.bayes import run_bayesian

if __name__ == "__main__":
    run_bayesian(Path(__file__).resolve().parents[1])
