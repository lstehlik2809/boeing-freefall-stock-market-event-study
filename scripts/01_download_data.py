from pathlib import Path
from boeing_event_study.download import download

if __name__ == "__main__":
    download(Path(__file__).resolve().parents[1])
