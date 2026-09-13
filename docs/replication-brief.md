# Boeing Event Study — Reproducibility Brief for Codex

## Task

Build a fully reproducible Python project that replicates a Bayesian event study of Boeing (BA) around three events:

1. **Alaska Airlines Flight 1282 / Boeing 737 MAX 9 door-plug incident**
   - Incident occurred: 2024-01-05
   - First tradable event day: **2024-01-08**

2. **U.S. Senate hearing with Boeing CEO Dave Calhoun**
   - Event/trading date: **2024-06-18**

3. **Netflix streaming release of _Freefall: A Reckoning for Boeing_**
   - Event/trading date: **2026-08-19**

Also run a sensitivity analysis using the documentary's earlier limited theatrical release:

- **2026-08-14**

The project must save all source code, downloaded data, processed data, results, plots, configuration, random seeds, and provenance information locally so another researcher can clone the repository and reproduce the results.

---

## 1. Repository structure

Create:

```text
boeing-event-study/
├── README.md
├── pyproject.toml
├── uv.lock
├── .gitignore
├── LICENSE
├── CITATION.cff
│
├── config/
│   ├── events.yml
│   ├── analysis.yml
│   └── event_contamination.csv
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── data_manifest.csv
│
├── src/
│   └── boeing_event_study/
│       ├── __init__.py
│       ├── download.py
│       ├── prepare.py
│       ├── bayes.py
│       ├── frequentist.py
│       ├── placebo.py
│       ├── plotting.py
│       └── utils.py
│
├── scripts/
│   ├── 01_download_data.py
│   ├── 02_prepare_data.py
│   ├── 03_run_bayesian_event_study.py
│   ├── 04_run_robustness_checks.py
│   ├── 05_make_figures.py
│   └── run_all.py
│
├── outputs/
│   ├── tables/
│   ├── figures/
│   ├── posterior/
│   └── logs/
│
├── tests/
│
└── report/
    └── results.md
```

`python scripts/run_all.py` should reproduce everything from the raw downloaded files.

---

## 2. Data

Use the public GitHub repository:

```text
zjplab/US-Trading-Data
```

Download and save locally these files:

```text
data/SP500/BA.csv
data/Indexes/^GSPC.csv
data/SP500/RTX.csv
data/SP500/LMT.csv
data/SP500/NOC.csv
data/SP500/GD.csv
data/SP500/TDG.csv
data/SP500/HWM.csv
```

Map them to:

```text
BA
GSPC
RTX
LMT
NOC
GD
TDG
HWM
```

**Do not analyze remote URLs directly.**

`01_download_data.py` must:

- download each CSV,
- save it under `data/raw/`,
- record source URL,
- download timestamp,
- number of rows,
- minimum and maximum date,
- file size,
- SHA-256 checksum

in:

```text
data/data_manifest.csv
```

Once downloaded, all later analysis must operate only on the local copies.

Add a `--skip-download` option so that a cloned repository can reproduce the analysis using an existing frozen data snapshot.

Before committing raw market data publicly, check whether redistribution is permitted by the upstream data source. If redistribution rights are unclear, do **not** put the CSVs in the public repository. Instead commit:

- the downloader,
- exact source paths,
- SHA-256 hashes,
- download date,
- manifest,
- processed-data construction code.

---

## 3. Return construction

Use the CSV `Close` column.

Compute simple daily returns:

```python
r_t = close_t / close_t_minus_1 - 1
```

Do not use log returns for the primary replication.

Align all series by trading date.

Construct the aerospace/defense peer return as an equal-weighted mean of:

```text
RTX
LMT
NOC
GD
TDG
HWM
```

On a date, require at least five of the six peer returns to be available.

Then construct:

```text
market_t = return of S&P 500 (^GSPC)

peer_t = equal-weighted peer return

sector_t = peer_t - market_t
```

Save the final aligned panel as:

```text
data/processed/daily_returns.csv
```

with columns at minimum:

```text
date
ba_return
market_return
peer_return
sector_return
ba_volume
```

---

## 4. Primary Bayesian counterfactual model

For each event separately estimate:

\[
R_{BA,t}
=
\alpha
+
\beta_M R_{Market,t}
+
\beta_S (R_{Peer,t}-R_{Market,t})
+
\epsilon_t
\]

with:

\[
\epsilon_t \sim StudentT(\nu=5,0,\sigma)
\]

Keep \(\nu=5\) fixed for the exact replication.

Use an estimation window of:

\[
[-250,-30]
\]

trading days relative to each event date.

This should produce **221 estimation observations per event**.

Match these priors from the original analysis:

```text
alpha       ~ Normal(0, 0.01)
beta_market ~ Normal(1, 1)
beta_sector ~ Normal(1, 1)
```

and:

```text
sigma² ~ InverseGamma(shape=2, scale=0.0004)
```

Use random seed:

```text
20260912
```

For the closest numerical replication, implement the Student-t likelihood using its normal/gamma scale-mixture representation and a Gibbs sampler.

Use:

```text
burn-in = 2,000 iterations
retained posterior draws = 4,000
thinning = 3
```

Save posterior draws for every event under:

```text
outputs/posterior/
```

preferably as compressed `.npz`, `.parquet`, or NetCDF.

---

## 5. Counterfactual abnormal returns

For every posterior draw \(s\), calculate expected Boeing return:

\[
\mu_t^{(s)}
=
\alpha^{(s)}
+
\beta_M^{(s)} R_{Market,t}
+
\beta_S^{(s)} Sector_t
\]

For the **primary** analysis, use the posterior predictive counterfactual.

For each event-period observation draw:

\[
\lambda_t^{(s)}
\sim Gamma(\nu/2,\nu/2)
\]

and:

\[
\epsilon_t^{(s)}
\sim
N\left(
0,
\sigma^{2(s)}/\lambda_t^{(s)}
\right)
\]

so the counterfactual untreated return is:

\[
R_t^{CF,(s)}
=
\mu_t^{(s)}+\epsilon_t^{(s)}
\]

and abnormal return:

\[
AR_t^{(s)}
=
R_{BA,t}^{obs}-R_t^{CF,(s)}
\]

Also calculate a secondary parameter-only quantity:

\[
AR_{mean,t}^{(s)}
=
R_{BA,t}^{obs}-\mu_t^{(s)}
\]

Do not confuse these two uncertainty concepts in the report.

---

## 6. Event windows

Calculate posterior CAR distributions for:

```text
[0,0]
[-1,+1]
[-3,+3]
[0,+5]
[0,+10]
```

For each, report:

```text
posterior median
posterior mean
95% credible interval
90% credible interval
P(CAR < 0)
P(CAR < -1%)
P(CAR < -3%)
P(|CAR| < 1%)
```

The last quantity is an informal practical-equivalence measure.

Save:

```text
outputs/tables/bayesian_event_windows.csv
```

---

## 7. Direct comparisons between events

Use independent posterior draws from each event to calculate:

```text
P(CAR_Alaska < CAR_Hearing)
P(CAR_Hearing < CAR_Netflix)
P(CAR_Alaska < CAR_Netflix)
P(CAR_Alaska < CAR_Hearing < CAR_Netflix)
```

Do this at least for:

```text
[-1,+1]
[0,+5]
```

Remember that these comparisons refer only to **these three particular events**.

Do not generalize them to populations of accidents, hearings, and documentaries.

---

## 8. Frequentist robustness model

For each event estimate the same market/sector model with OLS over the same `[-250,-30]` estimation period.

Compute conventional abnormal returns and CAR.

Also estimate a simpler market-only model:

\[
R_{BA,t}=\alpha+\beta R_{Market,t}+\epsilon_t
\]

Save both results.

---

## 9. Placebo / permutation-style robustness check

For each event window of length \(L\):

- take all possible consecutive \(L\)-day blocks of residuals from the pre-event OLS estimation period,
- sum residuals within each block,
- compare observed event CAR with this empirical distribution.

Report:

```text
lower-tail empirical p-value
two-sided empirical p-value
number of placebo windows
```

Use the finite-sample correction:

```python
p = (extreme_count + 1) / (n_placebos + 1)
```

Save:

```text
outputs/tables/placebo_results.csv
```

---

## 10. Abnormal trading volume

In each event's estimation period calculate:

```python
log_volume = log(BA volume)
```

Estimate mean and standard deviation.

For event days `-5` through `+10`, calculate:

```python
volume_z = (log(volume_t) - mean_estimation_log_volume) / sd_estimation_log_volume
```

Save to:

```text
outputs/tables/volume_event_study.csv
```

---

## 11. Netflix timing sensitivity

Repeat the full documentary analysis using:

```text
2026-08-14
```

as \(t=0\), corresponding to the earlier limited theatrical release.

Treat:

```text
2026-08-19
```

as the primary Netflix streaming event date.

Explicitly compare the conclusions.

---

## 12. Expected replication values

Use these as approximate tests of whether the implementation matches the original analysis.

Minor Monte Carlo differences are acceptable.

### Alaska event

```text
Event day:
median AR ≈ -9.29%
95% CrI ≈ [-12.02%, -6.56%]
P(AR < 0) ≈ 1.000

[-1,+1]:
median CAR ≈ -8.85%
95% CrI ≈ [-13.72%, -4.24%]
P(CAR < 0) ≈ 0.999

[0,+5]:
median CAR ≈ -22.20%
95% CrI ≈ [-28.78%, -15.27%]
```

### June 18 Senate hearing

```text
Event day:
median AR ≈ -2.17%
95% CrI ≈ [-5.36%, +1.16%]
P(AR < 0) ≈ 0.922

[-1,+1]:
median CAR ≈ -1.51%
95% CrI ≈ [-7.34%, +4.32%]
P(CAR < 0) ≈ 0.720

[0,+5]:
median CAR ≈ +1.26%
```

### Netflix streaming release

```text
Event day:
median AR ≈ +0.59%
95% CrI ≈ [-2.81%, +3.87%]
P(AR < 0) ≈ 0.339

[-1,+1]:
median CAR ≈ -1.32%
95% CrI ≈ [-7.20%, +4.55%]
P(CAR < 0) ≈ 0.699

[0,+5]:
median CAR ≈ -0.79%
95% CrI ≈ [-9.09%, +7.67%]
P(CAR < 0) ≈ 0.584

[0,+10]:
median CAR ≈ +1.41%
```

### Theatrical-release sensitivity

```text
t=0:       +0.07%
[-1,+1]:  -1.61%
[-3,+3]:  -2.82%
[0,+5]:   -2.71%
[0,+10]:  -4.01%
```

with wide credible intervals containing zero.

### Approximate direct comparison probabilities

```text
[-1,+1]:
P(Alaska < Hearing) ≈ 0.973
P(Hearing < Netflix) ≈ 0.524
P(Alaska < Netflix) ≈ 0.975

[0,+5]:
P(Alaska < Hearing) ≈ 1.000
P(Hearing < Netflix) ≈ 0.358
P(Alaska < Netflix) ≈ 1.000
```

### Approximate event-day abnormal-volume z scores

```text
Alaska:  +5.50 SD
Hearing: +0.02 SD
Netflix: -0.48 SD
```

If the results differ materially, stop and diagnose:

- return definition,
- date alignment,
- peer construction,
- estimation-window indexing,
- prior parameterization,
- Gamma rate versus scale conventions,
- Student-t mixture parameterization,
- random seed.

---

## 13. Figures

Produce publication-quality figures and save both PNG and SVG.

### Figure 1 — comparative CAR

Plot cumulative posterior abnormal return from trading day 0 through +10 for all three events.

Include:

- posterior median,
- 95% credible interval,
- horizontal zero line,
- relative trading-day x-axis.

### Figure 2 — event-window forest plot

For each event show median CAR and 95% CrI for:

```text
[-1,+1]
[-3,+3]
[0,+5]
```

### Figure 3 — abnormal trading volume

Plot volume z-score from `-5` through `+10` for all three events.

---

## 14. Causal-inference interpretation

The README/report must explicitly state that this is a **quasi-experimental event study**, not definitive proof of causal effects.

Frame the causal estimand as approximately:

> Boeing's return observed after the event minus the counterfactual return we would have expected on the same day had the focal event not occurred, conditional on contemporaneous broad-market and aerospace-sector movements.

Discuss these identification assumptions:

1. **No important simultaneous Boeing-specific confounder.**
2. **The pre-event market relationship remains valid during the event window.**
3. **The event contains sufficiently new information.**
4. **No major anticipation or information leakage occurs outside the chosen event window.**
5. **The market and peer portfolio are not themselves substantially affected by the focal Boeing-specific event.**

Also distinguish **identification strength**:

- Alaska: relatively strong for the immediate event-day shock because the incident was unexpected.
- Senate hearing: weaker because scrutiny was anticipated and much of the information was already public.
- Documentary: weakest because its content largely summarized previously public information and publicity/release timing was known beforehand.

Be particularly cautious interpreting Alaska's `[0,+5]` CAR as the effect of the original incident alone. Follow-on FAA actions, inspections, airline decisions, manufacturing revelations, and other Boeing news can become mediators or additional treatments. Therefore the cleanest causal interpretation is concentrated on the shortest windows.

---

## 15. Event contamination log

Create:

```text
config/event_contamination.csv
```

with:

```text
date
event
potentially_confounding_news
source
severity
notes
```

Research Boeing-specific news within at least ±5 trading days around each event.

Do **not** mechanically remove dates after seeing their returns.

Use this log to qualify interpretation rather than data-mine cleaner windows.

---

## 16. Reproducibility requirements

Ensure:

```bash
git clone ...
cd boeing-event-study
uv sync
uv run python scripts/run_all.py
```

is sufficient to regenerate all processed data, tables, and figures.

Set all random seeds explicitly.

Log:

```text
Python version
package versions
OS/platform
Git commit hash
random seed
analysis timestamp
raw-file SHA-256 hashes
```

to:

```text
outputs/logs/reproducibility.json
```

Do not overwrite original raw files silently. If a source file changes, detect the checksum difference and warn the user.

---

## 17. Tests

Add unit tests for:

- daily return calculation,
- date alignment,
- relative trading-day indexing,
- estimation-window length = 221,
- CAR summation,
- posterior summaries,
- placebo p-value calculation,
- SHA-256 manifest creation.

Add integration tests that check the approximate replication targets above.

Run with:

```bash
uv run pytest
```

---

## 18. Final README

The README should explain:

- research question,
- event definitions,
- data provenance,
- statistical model,
- Bayesian priors,
- event windows,
- counterfactual interpretation,
- robustness analyses,
- results,
- limitations,
- instructions for full reproduction,
- data licensing caveat.

Include a prominent warning:

> These results compare three individual historical events. They do not identify a general population-level effect of safety incidents, congressional hearings, or documentaries.

Also explain that a failure to detect a stock-price effect does **not** imply the documentary had no effect on reputation, trust, customer attitudes, employer attractiveness, or other outcomes.

---

## Recommended implementation details

Save **both the posterior-predictive CAR and the parameter-only expected-return CAR**, because they answer subtly different uncertainty questions.

Make the contamination log mandatory; for the Alaska event in particular, the very large `[0,+5]` estimate should not be casually interpreted as “the causal effect of the initial incident” because several consequential Boeing-related developments followed it.

For sharing, favor **GitHub + `uv.lock` + scripts + hashes** over a notebook-only project. A notebook may be added for exploration, but `run_all.py` should be the authoritative reproduction pipeline.

Optionally add a `Makefile` or `justfile` so the public workflow becomes:

```bash
uv sync
uv run python scripts/run_all.py
uv run pytest
```
