from pathlib import Path

from sar_scout.audit import AuditLog


def fill(path: Path, count: int = 3) -> AuditLog:
    log = AuditLog(path)
    for i in range(count):
        log.append({"i": i})
    return log


def test_chain_verifies(tmp_path: Path) -> None:
    assert fill(tmp_path / "a.jsonl", 5).verify()


def test_missing_file_verifies(tmp_path: Path) -> None:
    assert AuditLog(tmp_path / "never-written.jsonl").verify()


def test_edited_entry_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    fill(path)
    path.write_text(path.read_text().replace('"i": 1', '"i": 99'))
    assert not AuditLog(path).verify()


def test_deleted_entry_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    fill(path)
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert not AuditLog(path).verify()


def test_reopening_continues_the_chain(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    AuditLog(path).append({"i": 0})
    AuditLog(path).append({"i": 1})
    assert AuditLog(path).verify()
