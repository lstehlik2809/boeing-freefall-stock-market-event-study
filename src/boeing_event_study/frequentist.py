"""OLS market/sector and market-only robustness, residual placebos, and volume."""
from pathlib import Path

import numpy as np
import pandas as pd

from .placebo import placebo_pvalues
from .utils import design_matrix, load_config, read_panel, relative_slice


def fit_ols(X, y):
    beta, _, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    if rank < X.shape[1]:
        raise ValueError("OLS design is rank deficient")
    return beta, y - X @ beta


def volume_zscores(estimation_volume, event_volume):
    estimation, event = np.asarray(estimation_volume, dtype=float), np.asarray(event_volume, dtype=float)
    if len(estimation) < 2 or not np.isfinite(estimation).all() or not np.isfinite(event).all() or np.any(estimation <= 0) or np.any(event <= 0):
        raise ValueError("Volumes must be finite and strictly positive with at least two estimation days")
    mean, sd = np.log(estimation).mean(), np.log(estimation).std(ddof=1)
    if sd <= 0 or not np.isfinite(sd):
        raise ValueError("Estimation log volume must have nonzero sample variance")
    return (np.log(event) - mean) / sd, mean, sd


def run_robustness(root):
    root = Path(root)
    cfg, events = load_config(root)
    panel = read_panel(root)
    ols_rows, placebo_rows, volume_rows, coefficient_rows, daily_rows = [], [], [], [], []
    for event in events:
        required = ["ba_return", "market_return", "sector_return", "ba_volume"]
        estimation = relative_slice(panel, event["date"], *cfg["estimation_window"], required=required)
        period = relative_slice(panel, event["date"], *cfg["event_range"], required=required)
        for market_only in (False, True):
            specification = "market_only" if market_only else "market_sector"
            beta, residuals = fit_ols(design_matrix(estimation, market_only), estimation.ba_return.to_numpy())
            ar = period.ba_return.to_numpy() - design_matrix(period, market_only) @ beta
            for date, relative_day, observed, abnormal in zip(period.index, period.relative_day, period.ba_return, ar):
                daily_rows.append({"event": event["id"], "specification": specification, "date": str(date.date()),
                                   "relative_day": relative_day, "observed_return": observed,
                                   "expected_return": observed - abnormal, "abnormal_return": abnormal})
            coefficient_rows.append({"event": event["id"], "specification": specification,
                                     "alpha": beta[0], "beta_market": beta[1],
                                     "beta_sector": np.nan if market_only else beta[2], "n_estimation": len(estimation)})
            for label, (start, end) in cfg["windows"].items():
                mask = period.relative_day.between(start, end).to_numpy()
                car = ar[mask].sum()
                base = {"event": event["id"], "event_date": event["date"], "specification": specification,
                        "window": label, "n_days": end - start + 1, "car": car}
                ols_rows.append(base)
                placebo_rows.append({**base, **placebo_pvalues(car, residuals, end - start + 1)})
        z, mean, sd = volume_zscores(estimation.ba_volume, period.ba_volume)
        for date, row, score in zip(period.index, period.to_dict("records"), z):
            volume_rows.append({"event": event["id"], "event_date": event["date"], "date": str(date.date()),
                                "relative_day": row["relative_day"], "ba_volume": row["ba_volume"], "volume_z": score,
                                "estimation_log_volume_mean": mean, "estimation_log_volume_sd": sd})
    for filename, rows in (("frequentist_event_windows.csv", ols_rows), ("placebo_results.csv", placebo_rows),
                           ("volume_event_study.csv", volume_rows), ("ols_coefficients.csv", coefficient_rows),
                           ("frequentist_daily_returns.csv", daily_rows)):
        pd.DataFrame(rows).to_csv(root / "outputs/tables" / filename, index=False)
