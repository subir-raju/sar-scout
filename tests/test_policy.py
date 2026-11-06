from pathlib import Path

from sar_scout.models import DecisionAction
from sar_scout.policy import DenyZone, Policy, decide, load_policy


def test_low_score_is_denied(make_event) -> None:
    decision = decide(Policy(), make_event(), 0.1, 0)
    assert decision.action is DecisionAction.DENY


def test_deny_zone_beats_everything(make_event) -> None:
    zone = DenyZone(name="restricted", latitude=35.0,
                    longitude=139.0, radius_km=10)
    decision = decide(Policy(level=2, deny_zones=[
                      zone]), make_event(), 99.0, 0)
    assert decision.action is DecisionAction.DENY
    assert "restricted" in decision.reason


def test_deny_zone_boundary(make_event) -> None:
    # about 11.1 km north of the event
    zone = DenyZone(name="z", latitude=35.1, longitude=139.0, radius_km=12)
    assert decide(Policy(deny_zones=[zone]), make_event(
    ), 9.0, 0).action is DecisionAction.DENY
    zone = DenyZone(name="z", latitude=35.1, longitude=139.0, radius_km=10)
    assert decide(Policy(deny_zones=[zone]), make_event(
    ), 9.0, 0).action is not DecisionAction.DENY


def test_level_0_only_recommends(make_event) -> None:
    decision = decide(Policy(level=0), make_event(), 99.0, 0)
    assert decision.action is DecisionAction.RECOMMEND


def test_level_1_auto_submits_above_threshold(make_event) -> None:
    decision = decide(Policy(level=1), make_event(), 5.0, 0)
    assert decision.action is DecisionAction.AUTO_SUBMIT
    assert decision.policy_level == 1


def test_level_1_asks_below_threshold(make_event) -> None:
    decision = decide(Policy(level=1), make_event(), 1.0, 0)
    assert decision.action is DecisionAction.REQUEST_APPROVAL


def test_level_2_auto_submits_at_min_score(make_event) -> None:
    decision = decide(Policy(level=2), make_event(), 0.6, 0)
    assert decision.action is DecisionAction.AUTO_SUBMIT


def test_daily_cap_sends_work_to_a_human(make_event) -> None:
    policy = Policy(level=2, auto_daily_cap=2)
    assert decide(policy, make_event(), 5.0,
                  1).action is DecisionAction.AUTO_SUBMIT
    assert decide(policy, make_event(), 5.0,
                  2).action is DecisionAction.REQUEST_APPROVAL


def test_zero_cap_always_asks(make_event) -> None:
    decision = decide(Policy(level=2, auto_daily_cap=0), make_event(), 5.0, 0)
    assert decision.action is DecisionAction.REQUEST_APPROVAL


def test_hazard_outside_allow_list_asks_a_human(make_event) -> None:
    decision = decide(Policy(level=2), make_event(hazard="wildfire"), 5.0, 0)
    assert decision.action is DecisionAction.REQUEST_APPROVAL


def test_load_policy_from_toml(tmp_path: Path) -> None:
    path = tmp_path / "p.toml"
    path.write_text(
        'level = 2\nauto_daily_cap = 7\nallow_hazards = ["flood"]\n')
    policy = load_policy(path)
    assert (policy.level, policy.auto_daily_cap,
            policy.allow_hazards) == (2, 7, ["flood"])


def test_repository_policy_file_is_valid() -> None:
    policy = load_policy(Path(__file__).parents[1] / "policy.toml")
    assert policy.deny_zones and 0 <= policy.level <= 2
