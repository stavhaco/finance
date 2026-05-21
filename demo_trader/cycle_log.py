from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _preview(text: str, limit: int = 800) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 3].rstrip() + "..."


def _section_record(name: str, text: str, *, include_full: bool) -> dict[str, Any]:
    body = text or ""
    rec: dict[str, Any] = {
        "name": name,
        "chars": len(body),
        "lines": body.count("\n") + (1 if body else 0),
        "preview": _preview(body, 1200),
    }
    if include_full:
        rec["full"] = body
    return rec


def write_cycle_report(
    *,
    log_dir: str | Path,
    cycle_id: int,
    ts_utc_iso: str,
    payload: dict[str, Any],
    include_full_prompts: bool,
) -> Path:
    root = Path(log_dir)
    root.mkdir(parents=True, exist_ok=True)
    safe_ts = ts_utc_iso.replace(":", "").replace("+", "Z")[:20]
    path = root / f"cycle_{cycle_id:05d}_{safe_ts}.json"

    out = dict(payload)
    if "prompt" in out and isinstance(out["prompt"], dict):
        sections = out["prompt"].get("sections")
        if isinstance(sections, dict):
            out["prompt"] = {
                "ollama_model": out["prompt"].get("ollama_model"),
                "trading_allowed": out["prompt"].get("trading_allowed"),
                "sections": {
                    k: _section_record(k, str(v), include_full=include_full_prompts)
                    for k, v in sections.items()
                },
            }

    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
