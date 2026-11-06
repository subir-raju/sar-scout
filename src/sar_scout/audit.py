import hashlib
import json
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def _digest(previous: str, record: dict[str, Any]) -> str:
    body = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((previous + body).encode()).hexdigest()


class AuditLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._last = GENESIS
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._last = json.loads(line)["hash"]

    def append(self, record: dict[str, Any]) -> str:
        entry = {**record, "prev": self._last}
        entry["hash"] = _digest(self._last, record)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
        self._last = entry["hash"]
        return str(entry["hash"])

    def verify(self) -> bool:
        previous = GENESIS
        if not self.path.exists():
            return True
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            stored_hash, stored_prev = entry.pop("hash"), entry.pop("prev")
            if stored_prev != previous or _digest(previous, entry) != stored_hash:
                return False
            previous = stored_hash
        return True
