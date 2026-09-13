"""Recreate the portrait CAR comparison from saved posterior draws."""
from pathlib import Path

from boeing_event_study.plotting import make_linkedin_comparative_car


if __name__ == "__main__":
    make_linkedin_comparative_car(Path(__file__).resolve().parents[1])
