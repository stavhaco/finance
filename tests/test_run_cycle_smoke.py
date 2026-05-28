import subprocess
import sys
from pathlib import Path


def test_smoke_cycle_script_exits_zero() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "smoke_cycle.sh"
    assert script.is_file()
    proc = subprocess.run(
        [str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr[-2000:] + proc.stdout[-2000:]
