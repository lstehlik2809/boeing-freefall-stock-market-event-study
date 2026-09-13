"""Student-t scale-mixture Gibbs sampler with independent Normal coefficient priors."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .utils import design_matrix, load_config, read_panel, relative_slice


def coefficient_conditional(X, y, weights, sigma2, prior_mean, prior_sd):
    precision_prior = np.diag(1 / np.square(prior_sd))
    precision = precision_prior + X.T @ (weights[:, None] * X) / sigma2
    covariance = np.linalg.inv(precision)
    mean = np.linalg.solve(precision, precision_prior @ prior_mean + X.T @ (weights * y) / sigma2)
    return mean, covariance


def variance_conditional(residual, weights, shape, scale):
    # Coefficients have independent priors: no beta penalty and no +p/2 shape term.
    return shape + len(residual) / 2, scale + 0.5 * np.sum(weights * residual**2)


def mixture_conditional(residual, sigma2, nu):
    return (nu + 1) / 2, (nu + residual**2 / sigma2) / 2


def gibbs(X, y, model, rng):
    if not np.isfinite(X).all() or not np.isfinite(y).all() or len(y) != len(X):
        raise ValueError("Sampler input must be finite and aligned")
    prior_mean = np.asarray(model["prior_mean"], dtype=float)
    prior_sd = np.asarray(model["prior_sd"], dtype=float)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    sigma2 = max(float(np.mean((y - X @ beta)**2)), 1e-8)
    weights = np.ones(len(y))
    burn, retained, thin = model["burn_in"], model["retained_draws"], model["thinning"]
    if burn < 0 or retained < 1 or thin < 1:
        raise ValueError("Invalid sampler iteration settings")
    betas = np.empty((retained, X.shape[1]))
    variances = np.empty(retained)
    saved = 0
    for iteration in range(burn + retained * thin):
        mean, covariance = coefficient_conditional(X, y, weights, sigma2, prior_mean, prior_sd)
        beta = mean + np.linalg.cholesky(covariance) @ rng.standard_normal(X.shape[1])
        residual = y - X @ beta
        shape, scale = variance_conditional(residual, weights, model["sigma2_shape"], model["sigma2_scale"])
        sigma2 = 1 / rng.gamma(shape, 1 / scale)
        shape_lambda, rate_lambda = mixture_conditional(residual, sigma2, model["nu"])
        weights = rng.gamma(shape_lambda, 1 / rate_lambda)
        if iteration >= burn and (iteration - burn + 1) % thin == 0:
            betas[saved], variances[saved] = beta, sigma2
            saved += 1
    return betas, variances


def predictive_errors(sigma2, n_days, nu, rng):
    variances = np.asarray(sigma2)
    lambdas = rng.gamma(nu / 2, 2 / nu, size=(len(variances), n_days))
    return rng.standard_normal(lambdas.shape) * np.sqrt(variances[:, None] / lambdas)


def car_draws(ar, relative_days, start, end):
    mask = (relative_days >= start) & (relative_days <= end)
    if mask.sum() != end - start + 1:
        raise ValueError("CAR window lacks required trading observations")
    return ar[:, mask].sum(axis=1)


def summarize(draws):
    draws = np.asarray(draws)
    if draws.ndim != 1 or not np.isfinite(draws).all() or len(draws) == 0:
        raise ValueError("Summary requires a nonempty finite vector")
    q = np.quantile(draws, [0.025, 0.05, 0.5, 0.95, 0.975])
    return {"median": q[2], "mean": draws.mean(), "ci95_low": q[0], "ci95_high": q[4],
            "ci90_low": q[1], "ci90_high": q[3], "p_lt_0": np.mean(draws < 0),
            "p_lt_minus_1pct": np.mean(draws < -0.01), "p_lt_minus_3pct": np.mean(draws < -0.03),
            "p_abs_lt_1pct": np.mean(np.abs(draws) < 0.01)}


def event_streams(seed, event_id):
    # Stable named substreams do not depend on event execution order.
    key = int.from_bytes(hashlib.sha256(event_id.encode()).digest()[:4], "little")
    seeds = np.random.SeedSequence([seed, key]).spawn(2)
    return np.random.default_rng(seeds[0]), np.random.default_rng(seeds[1]), key


def compare_events(alaska, hearing, netflix):
    if not (alaska.shape == hearing.shape == netflix.shape):
        raise ValueError("Independent event arrays must have the same shape")
    return {"p_alaska_lt_hearing": np.mean(alaska < hearing),
            "p_hearing_lt_netflix": np.mean(hearing < netflix),
            "p_alaska_lt_netflix": np.mean(alaska < netflix),
            "p_alaska_lt_hearing_lt_netflix": np.mean((alaska < hearing) & (hearing < netflix))}


def chain_diagnostics(values):
    """Single-chain descriptive checks; these are not a convergence proof."""
    x = np.asarray(values)
    centered = x - x.mean()
    variance = np.dot(centered, centered)
    autocorrelations = [np.dot(centered[:-lag], centered[lag:]) / variance for lag in range(1, min(1000, len(x) // 2))]
    positive_pairs = []
    for i in range(0, len(autocorrelations) - 1, 2):
        pair = autocorrelations[i] + autocorrelations[i + 1]
        if pair <= 0:
            break
        positive_pairs.append(pair)
    ess = min(len(x), len(x) / (1 + 2 * sum(positive_pairs)))
    sd = x.std(ddof=1)
    batches = np.array_split(x, 20)
    mcse = np.std([b.mean() for b in batches], ddof=1) / np.sqrt(len(batches))
    return {"draw_mean": x.mean(), "draw_sd": sd, "lag1_autocorrelation": autocorrelations[0],
            "ess_approx": ess, "batch_mean_mcse": mcse,
            "first_half_mean": x[:len(x)//2].mean(), "second_half_mean": x[len(x)//2:].mean(),
            "half_difference_in_sd": abs(x[:len(x)//2].mean() - x[len(x)//2:].mean()) / sd}


def run_bayesian(root):
    root = Path(root)
    cfg, events = load_config(root)
    panel = read_panel(root)
    summary_rows, bounds, diagnostics, cache = [], [], [], {}
    required = ["ba_return", "market_return", "sector_return"]
    for event in events:
        estimation = relative_slice(panel, event["date"], *cfg["estimation_window"], required=required)
        period = relative_slice(panel, event["date"], *cfg["event_range"], required=required)
        if len(estimation) != 221:
            raise ValueError("Exact replication requires 221 estimation observations")
        sampler_rng, prediction_rng, key = event_streams(cfg["seed"], event["id"])
        beta, sigma2 = gibbs(design_matrix(estimation), estimation.ba_return.to_numpy(), cfg["model"], sampler_rng)
        mu = beta @ design_matrix(period).T
        cf = mu + predictive_errors(sigma2, len(period), cfg["model"]["nu"], prediction_rng)
        ar = period.ba_return.to_numpy()[None, :] - cf
        ar_mean = period.ba_return.to_numpy()[None, :] - mu
        days = period.relative_day.to_numpy()
        cars = {}
        for uncertainty, values in (("predictive", ar), ("parameter_only", ar_mean)):
            cars[uncertainty] = np.column_stack([car_draws(values, days, *window) for window in cfg["windows"].values()])
            for i, (label, window) in enumerate(cfg["windows"].items()):
                summary_rows.append({"event": event["id"], "event_date": event["date"], "uncertainty": uncertainty,
                                     "window": label, "start": window[0], "end": window[1], "n_days": window[1]-window[0]+1,
                                     **summarize(cars[uncertainty][:, i])})
        metadata = {"event": event, "seed": cfg["seed"], "event_seed_key": key,
                    "sampler_spawn_key": [0], "predictive_spawn_key": [1], "model": cfg["model"],
                    "estimation_start": str(estimation.index[0].date()), "estimation_end": str(estimation.index[-1].date()),
                    "estimation_n": len(estimation), "units": "decimal simple return, CAR=sum(AR)",
                    "coefficient_prior": "independent Normal, not scaled by sigma2"}
        np.savez_compressed(root / f"outputs/posterior/{event['id']}.npz", beta=beta, sigma2=sigma2,
                            dates=period.index.strftime("%Y-%m-%d").to_numpy(dtype=str), relative_days=days,
                            observed_return=period.ba_return.to_numpy(), mu=mu, counterfactual=cf,
                            ar_predictive=ar, ar_parameter_only=ar_mean,
                            car_predictive=cars["predictive"], car_parameter_only=cars["parameter_only"],
                            window_labels=np.asarray(list(cfg["windows"])), metadata_json=json.dumps(metadata))
        bounds.append({"event": event["id"], "event_date": event["date"], "estimation_start": metadata["estimation_start"],
                       "estimation_end": metadata["estimation_end"], "estimation_n": len(estimation),
                       "event_period_start": str(period.index[0].date()), "event_period_end": str(period.index[-1].date())})
        for j, name in enumerate(("alpha", "beta_market", "beta_sector", "sigma2")):
            diagnostics.append({"event": event["id"], "parameter": name,
                                **chain_diagnostics(beta[:, j] if j < 3 else sigma2)})
        cache[event["id"]] = cars
        print(f"Bayesian {event['id']}: {len(estimation)} estimation rows, {len(sigma2)} retained draws", flush=True)
    comparisons = []
    for uncertainty in ("predictive", "parameter_only"):
        for i, label in enumerate(cfg["windows"]):
            comparisons.append({"window": label, "uncertainty": uncertainty,
                                **compare_events(*(cache[name][uncertainty][:, i] for name in ("alaska", "hearing", "netflix")))})
    for filename, rows in (("bayesian_event_windows.csv", summary_rows), ("comparisons.csv", comparisons),
                           ("estimation_windows.csv", bounds), ("sampler_diagnostics.csv", diagnostics)):
        pd.DataFrame(rows).to_csv(root / "outputs/tables" / filename, index=False)
    return pd.DataFrame(summary_rows)
