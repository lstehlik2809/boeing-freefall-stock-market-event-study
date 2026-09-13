from pathlib import Path
from boeing_event_study.prepare import prepare

if __name__ == "__main__":
    prepare(Path(__file__).resolve().parents[1])
