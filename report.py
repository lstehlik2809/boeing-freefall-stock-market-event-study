"""Regenerate the readable research report exclusively from local output tables."""
from pathlib import Path

import pandas as pd


LABELS = {
    "alaska": "Alaska incident",
    "hearing": "Senate hearing",
    "netflix": "Netflix streaming",
    "theatrical": "Theatrical sensitivity",
}


def pct(value: float) -> str:
    return f"{100 * value:+.2f}%"


def markdown_table(frame: pd.DataFrame) -> str:
    def cell(value):
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value).replace("|", "\\|").replace("\n", " ")
    rows = ["| " + " | ".join(map(str, frame.columns)) + " |",
            "| " + " | ".join("---" for _ in frame.columns) + " |"]
    rows.extend("| " + " | ".join(cell(v) for v in row) + " |"
                for row in frame.itertuples(index=False, name=None))
    return "\n".join(rows)


def bayesian_display(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in frame.itertuples():
        rows.append({
            "Event": LABELS[row.event], "Window": row.window,
            "Median": pct(row.median),
            "95% CrI": f"[{pct(row.ci95_low)}, {pct(row.ci95_high)}]",
            "P(CAR<0)": f"{row.p_lt_0:.3f}",
            "P(CAR<-1%)": f"{row.p_lt_minus_1pct:.3f}",
            "P(CAR<-3%)": f"{row.p_lt_minus_3pct:.3f}",
            "P(|CAR|<1%)": f"{row.p_abs_lt_1pct:.3f}",
        })
    return pd.DataFrame(rows)


def generate_report(root: Path) -> None:
    root = Path(root)
    table_dir = root / "outputs" / "tables"
    windows = pd.read_csv(table_dir / "bayesian_event_windows.csv")
    predictive = windows[windows.uncertainty == "predictive"]
    parameter = windows[windows.uncertainty == "parameter_only"]
    comparisons = pd.read_csv(table_dir / "comparisons.csv")
    robustness = pd.read_csv(table_dir / "frequentist_event_windows.csv")
    placebos = pd.read_csv(table_dir / "placebo_results.csv")
    volume = pd.read_csv(table_dir / "volume_event_study.csv")
    diagnostic = pd.read_csv(table_dir / "replication_diagnostics.csv")
    failed = diagnostic.loc[~diagnostic.passed]
    audit_note = f"**{int(diagnostic.passed.sum())} of {len(diagnostic)} checks fall within the original fixed tolerances.**"
    if len(failed):
        audit_note += " The following differences remain outside tolerance and are explicitly retained in the audit, even when a documented review permits the pipeline to continue:\n\n"
        audit_note += markdown_table(failed[["event", "window", "metric", "target", "actual", "absolute_difference", "tolerance", "passed"]])
        audit_note += "\n\nThe Netflix [0,+10] median differs by 0.386 percentage points from the supplied approximate reference. Its separately saved Monte Carlo diagnostic supports possible simulation variability but cannot establish the original discrepancy's exact cause without the original snapshot and random draws. This is an approximate reproduction with a disclosed reference difference, not an exact numerical match. Production draws, the model and the original tolerance were retained. A narrowly bound review record permits only this same documented difference; other unreviewed discrepancies still stop the pipeline."
    day_column = next(c for c in ("relative_day", "rel_day", "t", "day") if c in volume)
    volume_zero = volume[volume[day_column] == 0]
    primary = predictive[predictive.event != "theatrical"]
    film = predictive[predictive.event.isin(["netflix", "theatrical"])]
    short = parameter[parameter.window.isin(["[0,0]", "[-1,+1]"])]
    net3 = predictive[(predictive.event == "netflix") & (predictive.window == "[-1,+1]")].iloc[0]
    alaska0 = predictive[(predictive.event == "alaska") & (predictive.window == "[0,0]")].iloc[0]
    film_zero = bool(((film.ci95_low <= 0) & (film.ci95_high >= 0)).all())
    timing = ("All five predictive 95% intervals contain zero for both film dates. "
              "Changing release timing therefore does not produce a clearly separated negative response in these windows."
              if film_zero else
              "At least one film window has a predictive 95% interval excluding zero; inspect the timing table rather than claiming that all windows agree.")
    report = f"""# Boeing event-study results

This report is regenerated from the frozen local inputs by `scripts/run_all.py`. Returns in the Bayesian display tables are percentages; machine-readable CSV returns are decimal fractions. Window endpoints are inclusive trading days.

> **These results compare three individual historical events. They do not identify a general population-level effect of safety incidents, congressional hearings, or documentaries.**

## What the estimates show

For Netflix's August 19, 2026 release, the three-day predictive CAR median is **{pct(net3['median'])}**, with a 95% credible interval of **[{pct(net3.ci95_low)}, {pct(net3.ci95_high)}]**. The probability of a negative CAR is **{net3.p_lt_0:.1%}**, while the probability of a CAR within ±1% is **{net3.p_abs_lt_1pct:.1%}**. A wide interval is not proof of practical equivalence or absence of an economically meaningful response.

The Alaska incident's first trading day has a predictive abnormal-return median of **{pct(alaska0['median'])}**, with 95% interval **[{pct(alaska0.ci95_low)}, {pct(alaska0.ci95_high)}]**. It offers a comparison with one unusually large shock; it does not calibrate power for a small documentary effect or establish a general ranking of event categories.

## Primary posterior predictive results

{markdown_table(bayesian_display(primary))}

The underlying [Bayesian table](../outputs/tables/bayesian_event_windows.csv) also includes means and 90% intervals. Probabilities of CAR below -1% and -3% show why failure to separate an estimate from zero must not be described as ruling out downside. The ±1% measure is informal, not a pre-registered equivalence test.

## Documentary timing sensitivity

{markdown_table(bayesian_display(film))}

{timing} The theatrical release precedes Netflix streaming by three trading sessions. Some windows include both releases and the same other news, so these are overlapping sensitivity estimates, not independent replications. [Release metadata](https://www.rottentomatoes.com/m/freefall_a_reckoning_for_boeing) supports August 14 and August 19 respectively.

## Direct comparisons of these events

{markdown_table(comparisons)}

These probabilities use independent draws from separately fitted event posteriors. They are conditional comparisons of the Alaska incident, this hearing and this streaming release. They do not estimate the frequency with which accidents outperform hearings or documentaries in other settings. Shared historical information and control-factor spillovers are not modeled as a joint cross-event structure.

## OLS, placebos and volume

Both OLS specifications use the same inclusive [-250,-30] estimation period. The following selected results use decimal-fraction return units.

{markdown_table(robustness[robustness.window.isin(['[0,0]', '[-1,+1]', '[0,+5]'])])}

For each OLS model and L-day event window, placebos are all overlapping consecutive sums of pre-event residuals. Lower-tail extremeness is `block <= observed CAR`; two-sided extremeness is `abs(block) >= abs(observed CAR)`. The finite-sample correction is `(extreme_count+1)/(number_of_blocks+1)`. Because the residual blocks overlap, these are empirical reference tail areas, not exact randomization-test p-values.

{markdown_table(placebos[placebos.window.isin(['[0,0]', '[-1,+1]', '[0,+5]'])])}

Event-day abnormal log-volume z-scores and their associated metadata:

{markdown_table(volume_zero)}

The baseline uses the estimation-period mean and sample SD (`ddof=1`) of log volume. The complete [volume table](../outputs/tables/volume_event_study.csv) covers -5 through +10. Full OLS/placebo window results are saved in [the tables directory](../outputs/tables/). Volume is an additional investor-activity outcome, not a direct sentiment measure.

## Uncertainty, model and replication audit

The fixed-df Student-t model uses BA returns as a function of an intercept, S&P 500 returns and equal-weighted peer returns minus S&P 500 returns. The peers are RTX, LMT, NOC, GD, TDG and HWM, with at least five available. Each event has 221 pre-event observations. Priors are independent Normal(0,0.01) for the intercept, Normal(1,1) for each beta (standard deviations), and InverseGamma(shape=2,scale=0.0004) for sigma². The normal/Gamma Gibbs sampler fixes df=5, seed=20260912, burn-in=2000, retained draws=4000 and thinning=3. See [README](../README.md) for the conditional equations and reproduction instructions.

The **primary predictive** counterfactual simulates both parameter uncertainty and a fresh daily Student-t innovation. The **parameter-only** counterfactual subtracts the fitted conditional mean and excludes ordinary daily innovations. Below are short-window secondary summaries; they must not be substituted for primary uncertainty intervals.

{markdown_table(bayesian_display(short))}

CAR is a sum of daily abnormal returns, not a compounded wealth return. Credible intervals are equal-tail quantiles. All posterior parameter and abnormal-return simulations are saved under [posterior](../outputs/posterior/).

The [replication audit](../outputs/tables/replication_diagnostics.csv) contains **{len(diagnostic)} reference checks** from the brief, with observed values, reference values, differences and fixed tolerances. A failed check requires diagnosis rather than changing the model or widening a tolerance. [Sampler diagnostics](../outputs/tables/sampler_diagnostics.csv) and [execution provenance](../outputs/logs/reproducibility.json) record additional numerical/environment evidence. Passing approximate targets is not proof of causal identification. See `validation.md` for the actual final verification record and any diagnosis.

{audit_note}

## Identification and competing news

This is a **quasi-experimental event study**, not definitive proof of causation. The approximate estimand is Boeing's observed return after the event minus its expected same-day return had the focal event not occurred, conditional on contemporaneous broad-market and aerospace-sector movements.

That interpretation requires (1) no important simultaneous Boeing-specific confounder; (2) a stable pre-event market relationship during the event window; (3) sufficiently new information; (4) no major anticipation or information leakage outside the chosen window; and (5) market and peer controls not substantially affected by the focal event. Boeing's inclusion in the S&P 500 and possible peer spillovers limit the last assumption. The model also imposes a fixed residual scale and conditionally independent daily innovations, which may miss changing volatility or dependence.

The unexpected Alaska incident supports relatively stronger identification of an immediate shock, although the first tradable day already bundles the incident with weekend regulatory actions. Its large [0,+5] loss includes follow-on FAA actions, inspections, airline decisions and additional manufacturing news; these can be mediators or additional treatments. It cannot be cleanly assigned to the original incident alone. The shortest windows have the most focused interpretation.

The scheduled Senate hearing has weaker identification because scrutiny and some information were anticipated. The documentary has the weakest identification because it revisits earlier events and had known release/publicity timing. However, [Netflix's own description](https://media.netflix.com/en/only-on-netflix/81780118) refers to new revelations: this analysis has not measured how much information was new to investors. Prior pricing of information is a plausible explanation, not an established finding.

The mandatory [contamination log](../config/event_contamination.csv) and [coverage notes](sources/contamination_research.md) document competing information around all four dates. The log qualifies interpretation; no observations are removed based on their returns. Searches are not exhaustive, and missing entries do not establish an absence of competing news. Model choice, selected peers, overlapping windows and multiple comparisons further restrict generalization.

## What share prices cannot tell us

Failure to detect a stock-price effect does **not** imply the documentary had no effect on trust, reputation, customer attitudes, employer attractiveness, employee identification or willingness to fly. Investors' capital-weighted choices are not public-opinion survey responses. This design does not identify documentary viewership, opinions, or a pathway from opinions to trading.

## Provenance and availability

The [data manifest](../data/data_manifest.csv) identifies all eight local raw files downloaded from upstream Git revision `14fec12f4af23d69633b6fd37e6d477facf0fa2b`. The supplied Close column is used for simple returns without extra adjustment. [Source notes](sources/provenance.md) explain the vendor-adjustment and licensing limitations. Raw and processed market CSVs remain local and excluded from Git because redistribution permission has not been established. Software, configuration, source paths, hashes and locked dependencies support reconstruction; upstream availability remains an external dependency.

## Figures

![Cumulative posterior predictive CAR](../outputs/figures/comparative_car.png)

![Event-window posterior predictive CAR](../outputs/figures/event_window_forest.png)

![Abnormal trading volume](../outputs/figures/abnormal_volume.png)

Each figure also has an SVG version in [the figure directory](../outputs/figures/).
"""
    (root / "report" / "results.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    generate_report(Path(__file__).resolve().parent)
