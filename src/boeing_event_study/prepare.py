"""Prepare a complete market-calendar panel without bridging missing observations."""
from pathlib import Path

import pandas as pd

from .download import parse_prices, verify_snapshot
from .utils import load_config


def simple_returns(close):
    return close / close.shift(1) - 1


def construct_panel(prices, peers, minimum_peers=5):
    calendar = prices["GSPC"].index
    closes = pd.DataFrame({ticker: frame.Close.reindex(calendar) for ticker, frame in prices.items()}, index=calendar)
    returns = simple_returns(closes)
    peer_returns = returns[peers]
    peer = peer_returns.mean(axis=1).where(peer_returns.notna().sum(axis=1) >= minimum_peers)
    return pd.DataFrame({"ba_return": returns.BA, "market_return": returns.GSPC, "peer_return": peer,
                         "sector_return": peer - returns.GSPC, "ba_volume": prices["BA"].Volume.reindex(calendar),
                         "peer_count": peer_returns.notna().sum(axis=1)}, index=calendar).rename_axis("date")


def prepare(root):
    root = Path(root)
    cfg, _ = load_config(root)
    verify_snapshot(root, cfg)
    prices = {ticker: parse_prices((root / f"data/raw/{ticker}.csv").read_bytes()) for ticker in cfg["source_paths"]}
    panel = construct_panel(prices, cfg["peers"], cfg["minimum_peers"])
    panel.to_csv(root / "data/processed/daily_returns.csv")
    return panel
