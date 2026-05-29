from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CycleTimer:
    """Per-phase wall times for a trading cycle (milliseconds in export)."""

    _starts: dict[str, float] = field(default_factory=dict)
    phases_ms: dict[str, int] = field(default_factory=dict)

    def start(self, phase: str) -> None:
        self._starts[phase] = time.perf_counter()

    def stop(self, phase: str) -> None:
        t0 = self._starts.pop(phase, None)
        if t0 is None:
            return
        ms = int((time.perf_counter() - t0) * 1000)
        self.phases_ms[phase] = self.phases_ms.get(phase, 0) + ms

    @property
    def total_ms(self) -> int:
        return sum(self.phases_ms.values())

    def to_json(self) -> str:
        payload: dict[str, Any] = {"phases_ms": dict(self.phases_ms), "total_ms": self.total_ms}
        return json.dumps(payload, ensure_ascii=False)
