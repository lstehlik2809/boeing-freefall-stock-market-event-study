"""Recreate the LinkedIn illustration from saved posterior summary results."""
from pathlib import Path

from boeing_event_study.plotting import make_linkedin_chart


if __name__ == "__main__":
    make_linkedin_chart(Path(__file__).resolve().parents[1])
