"""Recreate the standalone Freefall CAR chart from saved posterior draws."""
from pathlib import Path

from boeing_event_study.plotting import make_linkedin_freefall


if __name__ == "__main__":
    make_linkedin_freefall(Path(__file__).resolve().parents[1])
