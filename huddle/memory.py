from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class MemoryEntry:
    ts: str
    role: str
    content: str


class MemoryStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, role: str, content: str) -> None:
        entry = MemoryEntry(
            ts=datetime.now(UTC).isoformat(),
            role=role,
            content=content.strip(),
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=True) + "\n")

    def latest(self, limit: int = 12) -> list[MemoryEntry]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        items: list[MemoryEntry] = []
        for line in lines[-limit:]:
            if not line.strip():
                continue
            items.append(MemoryEntry(**json.loads(line)))
        return items

