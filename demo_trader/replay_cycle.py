"""Re-run trade LLM from a stored cycle log (prompt A/B on Mac)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from demo_trader.config import Config
from demo_trader.ollama_client import chat_json


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Replay Ollama trade decision from a cycle JSON log.")
    p.add_argument("cycle_log", type=Path, help="Path to data/logs/cycles/cycle_NNNNN_*.json")
    p.add_argument("--model", default=None, help="Override OLLAMA_MODEL")
    args = p.parse_args(argv)
    cfg = Config()
    model = args.model or cfg.ollama_model
    payload = json.loads(args.cycle_log.read_text(encoding="utf-8"))
    sections = (payload.get("prompt") or {}).get("sections") or {}
    system = sections.get("system") or ""
    user = sections.get("user") or ""
    if isinstance(system, dict):
        system = system.get("full") or system.get("preview") or ""
    if isinstance(user, dict):
        user = user.get("full") or user.get("preview") or ""
    if not system or not user:
        print("cycle log missing prompt sections", file=sys.stderr)
        return 2
    decision = chat_json(
        base_url=cfg.ollama_base_url,
        model=model,
        system=str(system),
        user=str(user),
        timeout_sec=cfg.ollama_timeout_sec,
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
