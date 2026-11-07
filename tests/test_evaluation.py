import math

import pytest

from sar_scout.evaluation import STRATEGIES, evaluate, format_table, run_strategy
from sar_scout.synthetic import generate_dataset


def test_a_run_is_reproducible_for_a_seed() -> None:
    items = generate_dataset(days=40, seed=2)
    first = run_strategy("scorer", items, daily_budget=1, seed=5)
    second = run_strategy("scorer", items, daily_budget=1, seed=5)

    assert first == second


def test_metrics_stay_within_bounds() -> None:
    items = generate_dataset(days=40, seed=2)
    for name in STRATEGIES:
        metrics = run_strategy(name, items, daily_budget=1, seed=0)
        assert 0 <= metrics.important_coverage <= 1
        assert 0 <= metrics.impact_capture <= 1.0
        assert metrics.rejected_attempts >= 0
        assert not math.isinf(metrics.mean_hours_to_image)


def test_unknown_strategy_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown strategy"):
        run_strategy("oracle", generate_dataset(
            days=5), daily_budget=1, seed=0)


def test_informed_strategies_beat_random_on_the_synthetic_world() -> None:
    # A sanity check of the harness, not a scientific result: the synthetic label depends on
    # severity by construction.
    results = evaluate(generate_dataset(
        days=120, seed=1), daily_budget=1, seeds=8)

    assert results["scorer"]["impact_capture"][0] > results["random"]["impact_capture"][0]
    assert results["severity"]["impact_capture"][0] > results["random"]["impact_capture"][0]


def test_table_lists_every_strategy() -> None:
    table = format_table(evaluate(generate_dataset(days=30, seed=1), seeds=2))

    assert all(name in table for name in STRATEGIES)
