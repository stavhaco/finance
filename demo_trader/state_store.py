from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class TradeRecord:
    ts: str
    symbol: str
    side: str
    qty: float
    price: float
    notional_ils: float
    reason: str


@dataclass
class SessionSnapshot:
    started_ts: str
    benchmark_symbol: str
    benchmark_start_px: float
    initial_nav_ils: float


@dataclass
class PaperState:
    cash_ils: float
    positions: dict[str, float] = field(default_factory=dict)
    trades: list[dict[str, Any]] = field(default_factory=list)
    session: SessionSnapshot | None = None
    last_cycle_ts: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "cash_ils": self.cash_ils,
            "positions": self.positions,
            "trades": self.trades,
            "last_cycle_ts": self.last_cycle_ts,
        }
        if self.session:
            d["session"] = asdict(self.session)
        return d

    @classmethod
    def from_json_dict(cls, raw: dict[str, Any]) -> PaperState:
        sess = raw.get("session")
        session: SessionSnapshot | None = None
        if isinstance(sess, dict) and sess:
            session = SessionSnapshot(
                started_ts=str(sess["started_ts"]),
                benchmark_symbol=str(sess["benchmark_symbol"]),
                benchmark_start_px=float(sess["benchmark_start_px"]),
                initial_nav_ils=float(sess["initial_nav_ils"]),
            )
        return cls(
            cash_ils=float(raw["cash_ils"]),
            positions={k: float(v) for k, v in (raw.get("positions") or {}).items()},
            trades=list(raw.get("trades") or []),
            session=session,
            last_cycle_ts=raw.get("last_cycle_ts"),
        )


def load_state(path: Path, starting_cash: float) -> PaperState:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        return PaperState(cash_ils=float(starting_cash))
    data = json.loads(path.read_text(encoding="utf-8"))
    return PaperState.from_json_dict(data)


def save_state(path: Path, state: PaperState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_json_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_trade(state: PaperState, rec: TradeRecord) -> None:
    state.trades.append(asdict(rec))
