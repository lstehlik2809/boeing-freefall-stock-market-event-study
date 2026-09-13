"""All overlapping consecutive residual-block placebos, with inclusive ties."""
import numpy as np


def placebo_distribution(residuals, length):
    residuals = np.asarray(residuals, dtype=float)
    if length < 1 or length > len(residuals) or not np.isfinite(residuals).all():
        raise ValueError("Invalid placebo residuals or window length")
    return np.convolve(residuals, np.ones(length), mode="valid")


def placebo_pvalues(observed_car, residuals, length):
    if not np.isfinite(observed_car):
        raise ValueError("Observed CAR must be finite")
    values = placebo_distribution(residuals, length)
    n = len(values)
    return {"p_lower": (np.sum(values <= observed_car) + 1) / (n + 1),
            "p_two_sided": (np.sum(np.abs(values) >= abs(observed_car)) + 1) / (n + 1),
            "n_placebos": n}
