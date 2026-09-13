"""AS-v1 numeric oracles for Gibbs conditionals, predictive t, CAR and OLS/placebos."""
import numpy as np
import pytest
from scipy.stats import t

from boeing_event_study.bayes import (car_draws, coefficient_conditional, compare_events, event_streams,
                                    gibbs, mixture_conditional, predictive_errors, summarize, variance_conditional)
from boeing_event_study.frequentist import fit_ols, volume_zscores
from boeing_event_study.placebo import placebo_distribution, placebo_pvalues


def test_gibbs_conditionals_independent_numeric_oracle():
    # Diagonal design makes the two scalar conjugate posteriors hand-computable.
    X, y = np.eye(2), np.array([3., 4.])
    mean, covariance = coefficient_conditional(X, y, np.array([2., 3.]), 2., np.array([1., -1.]), np.array([2., 1.]))
    np.testing.assert_allclose(mean, [2.6, 2.0])
    np.testing.assert_allclose(covariance, np.diag([.8, .4]))
    # IG does not include a beta-prior penalty or coefficient dimension term.
    shape, scale = variance_conditional(np.array([2., -1.]), np.array([3., 2.]), 2., .0004)
    assert shape == 3
    assert scale == pytest.approx(7.0004)
    shape, rate = mixture_conditional(np.array([2., -1.]), 2., 5.)
    assert shape == 3
    np.testing.assert_allclose(rate, [3.5, 2.75])


def test_seeded_sampler_retention_and_independent_streams():
    x = np.linspace(-1, 1, 30)
    X = np.column_stack([np.ones(len(x)), x, x*x])
    y = .003 + .4*x + .7*x*x + .01*np.sin(np.arange(30))
    model = {"prior_mean": [0, 1, 1], "prior_sd": [.01, 1, 1], "sigma2_shape": 2,
             "sigma2_scale": .0004, "nu": 5, "burn_in": 20, "retained_draws": 40, "thinning": 3}
    first = gibbs(X, y, model, np.random.default_rng(55))
    second = gibbs(X, y, model, np.random.default_rng(55))
    assert first[0].shape == (40, 3) and first[1].shape == (40,)
    np.testing.assert_array_equal(first[0], second[0])
    np.testing.assert_array_equal(first[1], second[1])
    assert (first[1] > 0).all()
    # Retaining every draw independently verifies the thinning schedule.
    unthinned = gibbs(X, y, {**model, "thinning": 1, "retained_draws": 120}, np.random.default_rng(55))
    np.testing.assert_array_equal(first[0], unthinned[0][2::3])
    a, ap, _ = event_streams(20260912, "alaska")
    b, bp, _ = event_streams(20260912, "hearing")
    a2, _, _ = event_streams(20260912, "alaska")
    draws_a = a.normal(size=100)
    np.testing.assert_array_equal(draws_a, a2.normal(size=100))
    assert not np.array_equal(draws_a, ap.normal(size=100))
    assert not np.array_equal(draws_a, b.normal(size=100))
    assert not np.array_equal(draws_a, bp.normal(size=100))


def test_predictive_mixture_matches_student_t_variance_and_quantiles():
    errors = predictive_errors(np.full(250_000, .0004), 1, 5, np.random.default_rng(9245)).ravel()
    assert errors.mean() == pytest.approx(0, abs=.00015)
    assert errors.var(ddof=1) == pytest.approx(.0004 * 5/3, rel=.03)
    np.testing.assert_allclose(np.quantile(errors, [.025, .5, .975]), .02*t.ppf([.025, .5, .975], 5), atol=.0005)


def test_car_and_summary_boundaries_hand_oracle():
    ar = np.array([[.01, -.02, -.03], [.02, .01, -.01]])
    np.testing.assert_allclose(car_draws(ar, np.array([-1, 0, 1]), -1, 1), [-.04, .02])
    np.testing.assert_allclose(car_draws(ar, np.array([-1, 0, 1]), 0, 0), [-.02, .01])
    with pytest.raises(ValueError, match="lacks"):
        car_draws(ar, np.array([-1, 0, 1]), -1, 2)
    values = np.array([-.03, -.01, 0, .01, .03])
    actual = summarize(values)
    assert actual["median"] == 0
    assert actual["mean"] == pytest.approx(0)
    assert actual["ci95_low"] == pytest.approx(-.028)
    assert actual["ci95_high"] == pytest.approx(.028)
    assert actual["ci90_low"] == pytest.approx(-.026)
    assert actual["ci90_high"] == pytest.approx(.026)
    assert actual["p_lt_0"] == .4
    assert actual["p_lt_minus_1pct"] == .2
    assert actual["p_lt_minus_3pct"] == 0
    assert actual["p_abs_lt_1pct"] == .2


def test_direct_comparisons_include_joint_strict_ordering():
    result = compare_events(np.array([0, 1, 2, 1]), np.array([1, 1, 0, 2]), np.array([2, 2, 1, 0]))
    assert result == {"p_alaska_lt_hearing": .5, "p_hearing_lt_netflix": .75,
                      "p_alaska_lt_netflix": .5, "p_alaska_lt_hearing_lt_netflix": .25}


@pytest.mark.parametrize("columns", [2, 3])
def test_ols_known_coefficients(columns):
    x = np.linspace(-1, 1, 17)
    X = np.column_stack([np.ones(len(x)), x, x*x])[:, :columns]
    expected = np.array([.01, 1.2, .8])[:columns]
    beta, residual = fit_ols(X, X@expected)
    np.testing.assert_allclose(beta, expected, atol=1e-12)
    np.testing.assert_allclose(residual, 0, atol=1e-12)


def test_placebo_all_overlapping_blocks_ties_and_correction():
    residual = np.array([-2, 1, -1, 2.])
    np.testing.assert_array_equal(placebo_distribution(residual, 2), [-1, 0, 1])
    assert placebo_pvalues(-1, residual, 2) == {"p_lower": .5, "p_two_sided": .75, "n_placebos": 3}
    assert placebo_pvalues(-9, residual, 2) == {"p_lower": .25, "p_two_sided": .25, "n_placebos": 3}
    assert placebo_pvalues(0, np.zeros(4), 1) == {"p_lower": 1, "p_two_sided": 1, "n_placebos": 4}
    assert len(placebo_distribution(np.arange(221), 11)) == 211


def test_volume_sample_sd_and_invalid_inputs():
    z, mean, sd = volume_zscores(np.exp([1., 2., 3.]), np.exp([2., 4.]))
    assert mean == pytest.approx(2)
    assert sd == pytest.approx(1)
    np.testing.assert_allclose(z, [0, 2], atol=1e-14)
    for invalid in ([0, 2], [-1, 2], [np.nan, 2], [np.inf, 2], [1, 1]):
        with pytest.raises(ValueError):
            volume_zscores(invalid, [1, 2])
    with pytest.raises(ValueError):
        volume_zscores([1, 2], [0])
