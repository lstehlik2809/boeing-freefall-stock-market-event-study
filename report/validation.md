# Validation and reference discrepancy

Initial analysis validation: 2026-09-12, with subsequent illustration updates on 2026-09-13. This document preserves the original numerical audit. The public repository now provides the software, result artifacts, and data reconstruction metadata described in the README. Repository publication does not publish the post to LinkedIn.

## Publication verification — 2026-09-13

A fresh Git clone of the prepared repository was created with its own virtual environment and **no raw or processed market CSVs**. `python -m uv sync --locked` succeeded, followed by the documented online `python -m uv run --locked python scripts/run_all.py`. All eight raw files were acquired from the pinned upstream URLs and passed the committed manifest checks. The complete pipeline succeeded with the expected 51/52 checks plus the documented reviewed difference.

All ten regenerated numerical result tables matched the existing results byte for byte, and every array in all four regenerated posterior archives matched exactly. The clean-clone test suite passed **54 tests in 38.31 seconds**, including the network-blocked rerun and reconstruction without derived outputs. Ruff and the lock-file check passed. README, data guide, validation, and results-report relative links resolved. The versioned file selection excludes raw/processed market CSVs, virtual environments, build artifacts, and internal implementation notes.

At initial publication, `outputs/logs/reproducibility.json` was copied from this verified clone. The log is refreshed as the project changes and records the current run's Git commit, working-tree status, environment, input hashes, and source-file hashes. The recorded commit can precede the commit of generated artifacts; consult the working-tree status and hashes as well. This verification used Windows / Python 3.10.7; it does not add an untested cross-platform claim.

## Approximate-reference audit

The initial production run stopped at the preset numerical diagnostic gate. **51 of 52 reference checks passed.** The remaining check was:

| Event/window | Metric | Brief target | Production value | Absolute difference | Original tolerance |
|---|---|---|---|---|---|
| Netflix [0,+10] | Predictive median CAR | +1.4100% | +1.7956% | 0.3856 percentage points | 0.3500 percentage points |

The failed flag is preserved in `outputs/tables/replication_diagnostics.csv`. The model, production random draws and tolerance were not changed to obtain a closer reference match.

### Diagnosis performed

Code and local inputs were checked for the supplied simple-return convention, local exchange dates, intact market-calendar alignment, six-peer construction with at least five available returns, inclusive 221-row estimation windows, independent coefficient priors, inverse-Gamma parameterization, Gamma rate versus scale, fixed Student-t degrees of freedom and explicit random streams. No implementation error explaining the discrepancy was found. The exact original raw snapshot, code and random draws were not supplied, so a unique original cause cannot be established.

The numerical diagnostic in `scripts/diagnose_predictive_mc.py` holds the saved coefficient/variance draws fixed and generates **32 independently seeded predictive replications of 4,000 draws each**. It does not replace the primary output. The diagnostic stream has entropy `[20260912, 999]`.

| Conditional diagnostic | Result |
|---|---|
| Parameter-only mean CAR | +1.5892% |
| Parameter-only median CAR | +1.5957% |
| Mean of 32 predictive replicate medians | +1.5903% |
| SD of replicate medians | 0.0757 percentage points |
| Range of replicate medians | [+1.3938%, +1.7197%] |
| Pooled 128,000-draw predictive median | +1.5889% |
| Brief target relative to replicate center | -2.38 replicate SD |
| Production median relative to replicate center | +2.71 replicate SD |

These checks demonstrate finite predictive-simulation variation and support its possible contribution. They **do not prove that the entire original discrepancy was caused by Monte Carlo error**. The production median is outside the observed range of these 32 diagnostic medians, and the supplied reference also lies in the lower part of the diagnostic distribution. These conditional replications do not include refitting variability of the coefficient chains. An exploratory larger simulation also put the center near +1.58%; the reproducible 32-replication diagnostic is the retained evidence used here.

The project therefore reports an **approximate reproduction with one reviewed reference difference**, rather than an exact numerical replication. The small absolute difference leaves the qualitative Netflix conclusion unchanged: the primary [0,+10] 95% interval is [-9.90%, +13.02%], which does not distinguish a clear direction.

The narrowly scoped resolution in `config/replication_resolutions.yml` allows only the same documented difference with matching source, dependency, configuration, manifest and archived-evidence hashes, plus the reviewed target and observed statistic within 1e-12 numerical roundoff. Unreviewed or changed discrepancies still stop the pipeline. A posterior-array fingerprint is separately audited; a byte-only difference is not itself a blocker, because platform/BLAS rounding can differ. The numerical `passed` field remains false for this check; review status is separate from that field. This implements the brief's instruction to stop and diagnose material differences, while preserving its allowance for approximate numerical replication.

The original reviewed diagnostic is saved as the immutable input `config/replication_review_evidence.json`. Each authoritative run independently regenerates the current diagnostic under `outputs/logs/` before applying the review gate. Removing derived outputs therefore does not remove a required input. Git attributes preserve versioned file bytes across checkouts instead of changing bound hashes through line-ending conversion.

## Data, windows and Monte Carlo inspection

Eight frozen raw files were downloaded from revision `14fec12f4af23d69633b6fd37e6d477facf0fa2b`. All end on 2026-09-11. Their byte hashes and source metadata are recorded in `data/data_manifest.csv` and verified before preparation.

| Event | Estimation start | Estimation end | Observations |
|---|---|---|---|
| Alaska | 2023-01-09 | 2023-11-22 | 221 |
| Hearing | 2023-06-21 | 2024-05-06 | 221 |
| Netflix | 2025-08-20 | 2026-07-08 | 221 |
| Theatrical | 2025-08-15 | 2026-07-02 | 221 |

Each event saves 4,000 retained posterior draws, 16 daily predictive and parameter-only abnormal returns per draw, and all five CAR windows. The main table contains 40 rows: four dates × five windows × two uncertainty concepts. The OLS and placebo tables each contain 40 rows; the volume table contains 64 rows.

Single-chain descriptive effective sample sizes for the 16 parameter/event combinations range from approximately 3,055 to 4,000. The largest first-half versus second-half mean difference is 0.067 posterior SD. The saved 4×4 trace plot was visually inspected: no obvious drift or stuck segment was seen. These checks are descriptive and do not prove convergence or causal identification.

All three required figures were visually inspected at their actual rendered PNGs. Labels, zero lines, event offsets, percentage units and uncertainty bands are legible and unclipped. The forest endpoints and cumulative day-5/day-10 summaries agree with the stored posterior summaries; volume day zero agrees with its table. Both PNG and SVG files are saved, together with supplemental sampler traces.

## Research and post

The 51-row contamination log covers researched calendar ranges corresponding to ±5 trading days around all four dates, including holidays/weekends and after-close timing qualifications. The longer +10 windows extend beyond that search scope. Sources and incomplete-access limitations are explicit; dates were not removed based on returns.

The current [updated LinkedIn post](../docs/linkedin-post.md) preserves the user's wording and structure, including the trading-app speculation, with numerical corrections and interpretive qualifications. The repository preparation adds a P.S. linking to the reproducibility materials. Historical condensed drafts and update notes are not included in this repository; the present document records the numerical reference discrepancy.

## Executed verification

Working directory for the commands below: `boeing-event-study/`. `python -m uv` was used because uv's executable was outside this machine's PATH. This is the same uv installation used by the documented `uv` commands.

| Check | Actual result |
|---|---|
| `python -m uv sync` | Environment resolved and installed; subsequent locked runs and lock validation succeeded |
| `python -m uv run --locked python scripts/run_all.py` | Successful online acquisition/full run; explicit 51/52 plus one reviewed-difference warning |
| `python -m uv run --locked python scripts/run_all.py --skip-download` | Successful final full regeneration from the local snapshot |
| `python -m uv run --locked pytest -q` | **54 passed**, no skipped tests, 36.70 seconds on the final implementation |
| `python -m uv run --locked ruff check src scripts tests` | Passed |
| `python -m uv lock --check` | Passed |
| `python -m uv build --no-sources` | Wheel and source distribution built successfully; no raw/processed market CSVs bundled |
| Generated report and supporting local links | No missing local link targets found |

The initial ordinary download/full-run evidence preceded the final clean-output correction; the final local rebuild and test suite exercise that corrected authoritative pipeline. There was no change to the downloader's network acquisition behavior during that correction.

The tests include an actual full rerun with socket connections blocked, comparing all ten CSV result tables byte-for-byte, every posterior array, and raw/manifest hashes. A second test copies source/configuration, the manifest and raw data into an isolated temporary project **without any derived outputs**. With network connections still blocked, the authoritative pipeline recreates the processed panel, posterior files, every table, current diagnostic, figures and report, and reproduces the same numerical results. These are process-level network restrictions in the test, not an operating-system firewall assertion.

Other tests cover hand-calculated simple returns and missing-data boundaries, five-peer availability, date/holiday indexing, the 221-row estimation window, independently evaluated Gibbs conditionals, predictive Student-t variation, strict probability thresholds, CAR sums, OLS, overlapping placebo blocks and ties, invalid volume, failed/changed downloads, manifest tampering, and the review gate's narrow rejection boundaries. A passing test suite does not change the one raw reference-check failure into a numerical pass.

The final review also added 18 negative cases for NaN and positive/negative infinity in the observed or expected target, actual value and tolerance. All are rejected before a reference difference can receive reviewed status. The final pipeline and test suite were rerun after that guard was added.

The verified runtime was Python **3.10.7** on Windows, NumPy **2.2.6**, pandas **2.3.3**, SciPy **1.15.3**, Matplotlib **3.10.9**, and PyYAML **6.0.3**. `.python-version` recommends the 3.10 series for fresh uv environments; `uv.lock` pins dependency resolution. The exact platform, versions, source hashes and current run timestamp are recorded in `outputs/logs/reproducibility.json`. A different operating system was not independently exercised here; floating-point bit identity across platforms is not asserted.
