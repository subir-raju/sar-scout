import json
from pathlib import Path

from typer.testing import CliRunner

from sar_scout.cli import app

runner = CliRunner()
POLICY = str(Path(__file__).parents[1] / "policy.toml")


def make_dataset(tmp_path: Path, days: str = "20") -> Path:
    path = tmp_path / "events.json"
    result = runner.invoke(
        app, ["synth", "--out", str(path), "--days", days, "--seed", "2"])
    assert result.exit_code == 0, result.output
    return path


def run_demo(tmp_path: Path, events: Path):
    db, audit = tmp_path / "demo.db", tmp_path / "audit.jsonl"
    args = [
        "demo", "--events", str(events), "--policy", POLICY,
        "--db", str(db), "--audit", str(audit), "--days", "10",
    ]  # fmt: skip
    return runner.invoke(app, args), db, audit


def test_synth_writes_a_dataset(tmp_path: Path) -> None:
    path = make_dataset(tmp_path, days="10")

    assert len(json.loads(path.read_text())) > 0


def test_demo_runs_and_the_audit_log_verifies(tmp_path: Path) -> None:
    result, _, audit = run_demo(tmp_path, make_dataset(tmp_path))

    assert result.exit_code == 0, result.output
    assert "Task summary" in result.output
    assert "audit log intact: True" in result.output
    assert runner.invoke(
        app, ["verify-audit", "--audit", str(audit)]).exit_code == 0


def test_verify_audit_fails_after_tampering(tmp_path: Path) -> None:
    _, _, audit = run_demo(tmp_path, make_dataset(tmp_path))
    audit.write_text(audit.read_text().replace(
        '"kind": "decision"', '"kind": "edited"', 1))

    assert runner.invoke(
        app, ["verify-audit", "--audit", str(audit)]).exit_code == 1


def test_eval_prints_a_comparison_table(tmp_path: Path) -> None:
    events = make_dataset(tmp_path, days="40")
    result = runner.invoke(
        app, ["eval", "--events", str(events), "--seeds", "2"])

    assert result.exit_code == 0
    assert "scorer" in result.output and "random" in result.output


def test_status_with_no_tasks(tmp_path: Path) -> None:
    result = runner.invoke(app, ["status", "--db", str(tmp_path / "empty.db")])

    assert "no tasks" in result.output
