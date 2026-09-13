"""Publication-sized figures with predictive uncertainty and explicit return units."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from .utils import load_config

COLORS = ["#0072B2", "#D55E00", "#009E73"]
SHORT_NAMES = {"alaska": "Alaska incident", "hearing": "Senate hearing", "netflix": "Netflix release", "theatrical": "Theatrical release"}


def save_figure(fig, root, stem):
    for suffix in ("png", "svg"):
        fig.savefig(Path(root) / f"outputs/figures/{stem}.{suffix}", dpi=220, bbox_inches="tight")
    plt.close(fig)


def add_car_baseline(ax, days, median, color, linewidth):
    """Show the preceding close as a defined origin, not an estimated daily AR."""
    ax.plot([-1, days[0]], [0, median[0]], color=color, linewidth=linewidth,
            linestyle="--", zorder=3)
    ax.plot(-1, 0, "o", color=color, markerfacecolor="white", markersize=5, zorder=4)
    ax.plot(days[0], median[0], "o", color=color, markersize=4, zorder=4)
    ax.set_xticks([-1, 0, 2, 4, 6, 8, 10],
                  ["Before\nevent", "0", "+2", "+4", "+6", "+8", "+10"])
    ax.get_xticklabels()[0].set_ha("right")


def make_linkedin_chart(root):
    """A single-window, three-row forest plot sized for a social-media post."""
    root = Path(root)
    summary = pd.read_csv(root / "outputs/tables/bayesian_event_windows.csv")
    rows = summary[(summary.uncertainty == "predictive") & (summary.window == "[-1,+1]")]
    rows = rows[rows.event.isin(["alaska", "hearing", "netflix"])].set_index("event")
    if len(rows) != 3 or not rows.index.is_unique:
        raise ValueError("LinkedIn chart requires exactly one predictive three-day row per primary event")
    rows = rows.loc[["alaska", "hearing", "netflix"]]
    if not np.isfinite(rows[["median", "ci95_low", "ci95_high"]].to_numpy()).all():
        raise ValueError("LinkedIn chart requires finite posterior summaries")

    ink, muted, teal = "#192D3A", "#60717D", "#008879"
    with plt.rc_context({"font.family": "DejaVu Sans", "svg.fonttype": "none"}):
        fig = plt.figure(figsize=(10, 8.8), facecolor="#FFFFFF")
        fig.text(.065, .935, "Did Freefall move", fontsize=29, fontweight="bold", color=ink)
        fig.text(.065, .880, "Boeing’s share price?", fontsize=29, fontweight="bold", color=ink)
        fig.text(.065, .823, "Three-day abnormal returns around three Boeing events",
                 fontsize=14, color=muted)

        ax = fig.add_axes([.315, .285, .625, .465], facecolor="none")
        ax.set(xlim=(-.16, .06), ylim=(-.62, 2.62), yticks=[],
               xticks=[-.15, -.10, -.05, 0, .05])
        ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.tick_params(axis="x", labelsize=12, colors=muted, length=0, pad=10)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(axis="x", color="#E6EBEE", linewidth=.8, zorder=0)
        ax.axvline(0, color="#60717D", linewidth=1.3, zorder=1)
        ax.set_xlabel("Cumulative abnormal return", fontsize=12, color=muted, labelpad=13)

        names = {"alaska": "Alaska Airlines\nincident", "hearing": "Senate hearing",
                 "netflix": "Netflix release"}
        dates = {"alaska": "First trading day: 8 Jan 2024", "hearing": "18 June 2024", "netflix": "19 August 2026"}
        for y, (event, row) in zip([2, 1, 0], rows.iterrows()):
            color = teal if event == "netflix" else muted
            if event == "netflix":
                ax.axhspan(-.42, .42, color="#E9F6F2", zorder=-1)
            low, median, high = row.ci95_low, row["median"], row.ci95_high
            ax.plot([low, high], [y, y], color=color, linewidth=3.2, zorder=3)
            ax.plot([low, high], [y, y], linestyle="none", marker="|", markersize=14,
                    markeredgewidth=2, color=color, zorder=3)
            ax.plot(median, y, "o", color=color, markersize=10, zorder=4)
            ax.text(median, y + .18, f"{median:+.1%}".replace("-", "−"),
                    ha="center", va="bottom", fontsize=19, fontweight="bold", color=color)
            for value in (low, high):
                ax.text(value, y - .18, f"{value:+.1%}".replace("-", "−"),
                        ha="center", va="top", fontsize=11, color=color)
            figure_y = .285 + .465 * (y + .62) / 3.24
            fig.text(.065, figure_y + .012, names[event], fontsize=15.5,
                     fontweight="bold" if event == "netflix" else "medium", color=color, va="center")
            fig.text(.065, figure_y - .049, dates[event], fontsize=10.5, color=muted, va="center")

        fig.text(.065, .178, "Dot: posterior median   ·   Bar: 95% predictive credible interval",
                 fontsize=11.5, color=ink)
        fig.text(.065, .126, "Window: the trading day before, event day and day after [−1,+1].",
                 fontsize=11, color=muted)
        fig.text(.065, .080, "Three individual events. Model-based estimates; causal attribution remains uncertain.",
                 fontsize=10, color=muted)
        fig.text(.065, .046, "Source: frozen Boeing event-study results · 4,000 posterior draws per event",
                 fontsize=9.5, color=muted)
        output = root / "outputs/figures"
        output.mkdir(parents=True, exist_ok=True)
        for suffix in ("png", "svg"):
            fig.savefig(output / f"linkedin_three_day_forest.{suffix}", dpi=200, facecolor="white")
        plt.close(fig)


def make_linkedin_comparative_car(root):
    """Portrait, vertically stacked CAR comparison with identical panel scales."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    root = Path(root)
    events = [
        ("alaska", "Alaska Airlines incident", "First trading day: 8 January 2024", "#0072B2"),
        ("hearing", "Senate hearing", "18 June 2024", "#D55E00"),
        ("netflix", "Netflix release", "19 August 2026", "#008879"),
    ]
    curves = {}
    for event, _, _, _ in events:
        with np.load(root / f"outputs/posterior/{event}.npz") as draws:
            mask = (draws["relative_days"] >= 0) & (draws["relative_days"] <= 10)
            days = draws["relative_days"][mask]
            ar = draws["ar_predictive"][:, mask]
        if not np.array_equal(days, np.arange(11)) or not np.isfinite(ar).all():
            raise ValueError("LinkedIn CAR chart requires finite predictive draws for days 0 through +10")
        curves[event] = np.quantile(ar.cumsum(axis=1), [.025, .5, .975], axis=0)

    minimum = int(np.floor(min(curve[0].min() for curve in curves.values()) * 10))
    maximum = int(np.ceil(max(curve[2].max() for curve in curves.values()) * 10))
    ticks = np.arange(minimum, maximum + 1) / 10
    ink, muted = "#192D3A", "#60717D"
    with plt.rc_context({"font.family": "DejaVu Sans", "svg.fonttype": "none"}):
        fig = plt.figure(figsize=(10, 12.5), facecolor="white")
        fig.text(.075, .953, "Boeing’s abnormal returns", fontsize=27, fontweight="bold", color=ink)
        fig.text(.075, .908, "after three events", fontsize=27, fontweight="bold", color=ink)
        fig.text(.075, .863, "Cumulative abnormal returns from event day to day +10",
                 fontsize=13.5, color=muted)
        fig.legend(handles=[Line2D([0], [0], color=muted, linewidth=3, label="Posterior median"),
                            Patch(facecolor=muted, alpha=.20, edgecolor="none",
                                  label="95% predictive credible interval")],
                   loc="upper left", bbox_to_anchor=(.066, .852), ncol=2,
                   frameon=False, fontsize=11.5, columnspacing=1.6)

        for bottom, (event, name, date, color) in zip([.610, .380, .150], events):
            low, median, high = curves[event]
            ax = fig.add_axes([.115, bottom, .825, .155])
            ax.set_facecolor("#F3FAF8" if event == "netflix" else "white")
            ax.fill_between(days, low, high, color=color, alpha=.19, linewidth=0, zorder=1)
            ax.plot(days, median, color=color, linewidth=3, zorder=3)
            ax.plot(days[-1], median[-1], "o", color=color, markersize=5, zorder=4)
            ax.axhline(0, color=muted, linewidth=1.1, zorder=2)
            ax.set(xlim=(-1.3, 10.15), ylim=(minimum / 10 - .02, maximum / 10 + .01),
                   yticks=ticks)
            add_car_baseline(ax, days, median, color, linewidth=2)
            ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
            ax.tick_params(axis="both", labelsize=12, colors=muted, length=0, pad=7)
            ax.tick_params(axis="x", labelbottom=event == "netflix")
            ax.grid(axis="y", color="#DCE4E9", linewidth=.7, alpha=.7, zorder=0)
            ax.set_axisbelow(True)
            for spine in ax.spines.values():
                spine.set_visible(False)
            fig.text(.115, bottom + .193, name, fontsize=17, fontweight="bold", color=color)
            fig.text(.115, bottom + .174, date, fontsize=10.5, color=muted)
            label = f"Day +10: {median[-1]:+.1%}".replace("-", "−")
            fig.text(.940, bottom + .187, label, fontsize=13, fontweight="bold", color=color, ha="right")

        fig.text(.525, .094, "Trading days from event", fontsize=13, color=ink, ha="center")
        fig.text(.075, .066, "Before event: preceding close, set to zero. Day 0 includes the first trading day’s return.",
                 fontsize=10, color=muted)
        fig.text(.075, .043, "Same scale. Three events; overlapping news limits causal attribution.", fontsize=10, color=muted)
        fig.text(.075, .020, "Source: frozen Boeing event study · 4,000 posterior draws per event", fontsize=9.5, color=muted)
        output = root / "outputs/figures"
        output.mkdir(parents=True, exist_ok=True)
        for suffix in ("png", "svg"):
            fig.savefig(output / f"linkedin_comparative_car_vertical.{suffix}", dpi=200, facecolor="white")
        plt.close(fig)


def make_figures(root):
    root = Path(root)
    _, events = load_config(root)
    primary = [event for event in events if event["primary"]]
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "figure.facecolor": "white"})
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.9), sharey=True, layout="constrained")
    for ax, event, color in zip(axes, primary, COLORS):
        with np.load(root / f"outputs/posterior/{event['id']}.npz") as draws:
            mask = draws["relative_days"] >= 0
            days = draws["relative_days"][mask]
            car = draws["ar_predictive"][:, mask].cumsum(axis=1)
        low, median, high = np.quantile(car, [.025, .5, .975], axis=0)
        ax.fill_between(days, low, high, color=color, alpha=.19, label="95% credible interval")
        ax.plot(days, median, color=color, linewidth=2, label="Posterior median")
        ax.axhline(0, color="0.35", linewidth=.8)
        ax.set(title=SHORT_NAMES[event["id"]], xlabel="Trading days from event", xlim=(-1.3, 10.15))
        add_car_baseline(ax, days, median, color, linewidth=1.5)
        ax.tick_params(axis="x", labelsize=9)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.grid(axis="y", alpha=.18)
    axes[0].set_ylabel("Cumulative abnormal return")
    axes[-1].legend(loc="lower left", fontsize=9)
    fig.suptitle("Boeing cumulative abnormal returns · posterior predictive counterfactual", fontsize=13)
    fig.supxlabel("Before event: preceding close, set to zero. Day 0 includes the first trading day’s return.", fontsize=10)
    save_figure(fig, root, "comparative_car")

    summary = pd.read_csv(root / "outputs/tables/bayesian_event_windows.csv")
    windows = ["[-1,+1]", "[-3,+3]", "[0,+5]"]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.1), sharex=True, layout="constrained")
    for ax, event, color in zip(axes, primary, COLORS):
        rows = summary.query("uncertainty == 'predictive'")
        rows = rows[rows.event == event["id"]].set_index("window").loc[windows]
        ax.errorbar(rows["median"], np.arange(3), xerr=np.vstack((rows["median"] - rows.ci95_low, rows.ci95_high - rows["median"])),
                    fmt="o", color=color, capsize=5, markersize=6, linewidth=2)
        ax.axvline(0, color="0.35", linewidth=.8)
        ax.set(yticks=np.arange(3), yticklabels=windows, ylim=(2.5, -.5), title=SHORT_NAMES[event["id"]], xlabel="Cumulative abnormal return")
        ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.grid(axis="x", alpha=.18)
    fig.suptitle("Event-window posterior medians and 95% credible intervals · predictive", fontsize=13)
    save_figure(fig, root, "event_window_forest")

    volume = pd.read_csv(root / "outputs/tables/volume_event_study.csv")
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.1), sharey=True, layout="constrained")
    for ax, event, color in zip(axes, primary, COLORS):
        rows = volume[volume.event == event["id"]]
        ax.plot(rows.relative_day, rows.volume_z, color=color, marker="o", markersize=3)
        ax.axhline(0, color="0.35", linewidth=.8)
        ax.axvline(0, color="0.35", linewidth=.8, linestyle="--")
        ax.set(title=SHORT_NAMES[event["id"]], xlabel="Trading days from event", xticks=[-5, 0, 5, 10])
        ax.grid(axis="y", alpha=.18)
    axes[0].set_ylabel("Log-volume z-score (estimation sample SD)")
    fig.suptitle("Boeing abnormal trading volume", fontsize=13)
    save_figure(fig, root, "abnormal_volume")

    fig, axes = plt.subplots(4, 4, figsize=(14, 10), layout="constrained")
    for row, event in enumerate(events):
        with np.load(root / f"outputs/posterior/{event['id']}.npz") as draws:
            parameters = np.column_stack([draws["beta"], draws["sigma2"]])
        for col, label in enumerate(("alpha", "beta market", "beta sector", "sigma squared")):
            axes[row, col].plot(parameters[:, col], linewidth=.45, alpha=.65)
            axes[row, col].set_title(f"{SHORT_NAMES[event['id']]} · {label}", fontsize=10)
            if row == 3:
                axes[row, col].set_xlabel("Retained draw index")
    fig.suptitle("Single-chain sampler traces after burn-in (descriptive diagnostics)")
    save_figure(fig, root, "supplement_sampler_traces")
    make_linkedin_chart(root)
    make_linkedin_comparative_car(root)
