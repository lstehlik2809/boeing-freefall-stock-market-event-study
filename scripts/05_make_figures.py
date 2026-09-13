from pathlib import Path
from boeing_event_study.plotting import make_figures

if __name__ == "__main__":
    make_figures(Path(__file__).resolve().parents[1])
