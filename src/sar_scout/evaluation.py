import random
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone

from sar_scout.dataset import LabeledEvent
from sar_scout.mock_service import accept_probability
from sar_scout.scoring import ImageRecord, score_event

STRATEGIES = ("random", "severity", "scorer")
METRICS = ("important_coverage", "impact_capture",
           "rejected_attempts", "mean_hours_to_image")


@dataclass
class RunMetrics:
    # share of the top 20% events (by impact) that got imaged
    important_coverage: float
    impact_capture: float       # impact imaged, divided by what a perfect picker could image
    rejected_attempts: float    # submissions the (simulated) API refused
    mean_hours_to_image: float  # event time to image time, for important events


def run_strategy(
    name: str,
    items: Sequence[LabeledEvent],
    *,
    daily_budget: int,
    seed: int,
    important_quantile: float = 0.8,
    max_attempts: int = 3,
    base_window: int = 12,
) -> RunMetrics:
    if name not in STRATEGIES:
        raise ValueError(f"unknown strategy {name!r}")
    rng = random.Random(seed)
    impacts = sorted(item.impact for item in items)
    threshold = impacts[min(
        len(impacts) - 1, int(len(impacts) * important_quantile))]
    important = {item.event.id for item in items if item.impact >= threshold}

    by_day: dict[date, list[LabeledEvent]] = defaultdict(list)
    for item in sorted(items, key=lambda item: item.event.observed_at):
        by_day[item.event.observed_at.date()].append(item)

    images: list[ImageRecord] = []
    imaged_important: set[str] = set()
    captured = oracle = rejected = 0.0
    hours: list[float] = []

    for day in sorted(by_day):
        todays = by_day[day]
        end = datetime(day.year, day.month, day.day,
                       tzinfo=timezone.utc) + timedelta(days=1)
        oracle += sum(sorted((item.impact for item in todays),
                      reverse=True)[:daily_budget])
        if name == "random":
            picks = rng.sample(todays, min(daily_budget, len(todays)))
        elif name == "severity":
            picks = sorted(todays, key=lambda item: -
                           item.event.severity)[:daily_budget]
        else:
            picks = sorted(todays, key=lambda item: -
                           score_event(item.event, end, images))
            picks = picks[:daily_budget]
        for item in picks:
            for attempt in range(max_attempts):
                window = base_window * 2**attempt
                if rng.random() < accept_probability(window):
                    captured += item.impact
                    latency = rng.uniform(2, window)
                    if item.event.id in important:
                        imaged_important.add(item.event.id)
                        waited = (
                            end - item.event.observed_at).total_seconds() / 3600
                        hours.append(waited + latency)
                    images.append(ImageRecord(
                        item.event.latitude, item.event.longitude, end))
                    break
                rejected += 1

    return RunMetrics(
        important_coverage=len(imaged_important) / max(1, len(important)),
        impact_capture=captured / oracle if oracle else 0.0,
        rejected_attempts=rejected,
        mean_hours_to_image=statistics.fmean(hours) if hours else float("nan"),
    )


# strategy -> metric -> (mean, std)
Results = dict[str, dict[str, tuple[float, float]]]


def evaluate(items: Sequence[LabeledEvent], *, daily_budget: int = 1, seeds: int = 20) -> Results:
    results: Results = {}
    for name in STRATEGIES:
        runs = [
            asdict(run_strategy(name, items, daily_budget=daily_budget, seed=seed))
            for seed in range(seeds)
        ]
        results[name] = {
            metric: (
                statistics.fmean(run[metric] for run in runs),
                statistics.pstdev(run[metric] for run in runs),
            )
            for metric in METRICS
        }
    return results


def format_table(results: Results) -> str:
    header = f"{'strategy':<10} " + \
        " ".join(f"{metric:>22}" for metric in METRICS)
    lines = [header, "-" * len(header)]
    for name, metrics in results.items():
        cells = " ".join(
            f"{metrics[m][0]:>14.3f} ±{metrics[m][1]:>6.3f}" for m in METRICS)
        lines.append(f"{name:<10} {cells}")
    return "\n".join(lines)


def plot(results: Results, path: str) -> None:
    """Save a bar chart. Needs the optional ``eval`` extra (matplotlib)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = list(results)
    figure, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    panels = (
        ("important_coverage", "Important events imaged"),
        ("impact_capture", "Impact captured vs perfect picker"),
        ("mean_hours_to_image", "Hours to image (important)"),
    )
    for axis, (metric, title) in zip(axes, panels, strict=True):
        axis.bar(
            names,
            [results[name][metric][0] for name in names],
            yerr=[results[name][metric][1] for name in names],
            capsize=4,
            color=["#9aa5b1", "#7fa7c0", "#d7442b"],
        )
        axis.set_title(title, fontsize=11)
    figure.suptitle(
        "Tasking strategies under a fixed daily budget (mean ± std over seeds)")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
