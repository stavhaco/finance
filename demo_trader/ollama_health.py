from __future__ import annotations

import requests


def ollama_reachable(base_url: str, *, timeout_sec: float = 5.0) -> tuple[bool, str]:
    """Return (ok, detail) for GET /api/tags."""
    url = base_url.rstrip("/") + "/api/tags"
    try:
        r = requests.get(url, timeout=timeout_sec)
        if r.status_code == 200:
            return True, "ok"
        return False, f"HTTP {r.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "connection refused (is `ollama serve` running?)"
    except requests.exceptions.Timeout:
        return False, "timeout"
    except Exception as e:
        return False, str(e)[:200]


def format_ollama_help(base_url: str, model: str) -> str:
    return (
        f"Ollama not reachable at {base_url}.\n"
        "  Mac: open Ollama.app or run `ollama serve`, then `ollama pull "
        f"{model}`.\n"
        "  Linux/cloud agent: `./scripts/ci/setup_ollama.sh` then re-run.\n"
        "  Mac bridge: ./scripts/mac/enable_ollama_lan.sh then "
        "OLLAMA_BASE_URL in scripts/ci/remote-ollama.env (see README).\n"
        "  CI without GPU: `DEMO_TRADER_DRY_RUN=1 python -m demo_trader --once --dry-run`."
    )
