"""월간 beopjungri 매칭 품질 게이트 — pipeline/verify_beopjungri_mapping.py 래퍼."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "pipeline" / "verify_beopjungri_mapping.py"


def main() -> None:
    cmd = [sys.executable, str(_SCRIPT), *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd, cwd=str(_REPO / "pipeline")))


if __name__ == "__main__":
    main()
