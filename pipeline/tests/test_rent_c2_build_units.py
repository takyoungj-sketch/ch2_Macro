"""판정 생성기의 합성 출력. 전체 재측정은 하지 않는다."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.rent import rent_c2_build_units as gen  # noqa: E402


def _row(lot: str, part: int) -> dict:
    return {
        "base_key": "b",
        "asset_type": "apartment",
        "beopjungri_code": "1111010100",
        "main_lot": lot,
        "part": part,
        "decision": "split",
        "evidence": "title_register",
        "source": gen.SOURCE,
        "collective_sha256": gen.COLLECTIVE_SHA,
        "note": "",
    }


def test_synthetic_rows_have_sha_format(tmp_path: Path):
    path = tmp_path / "units.csv"
    rows = [_row("2", 1), _row("10", 0)]
    digest = gen.write_units_csv(list(reversed(rows)), path)
    text = path.read_text(encoding="utf-8")
    body = [line for line in text.splitlines() if line and not line.startswith("base_key")]
    assert len(body) == 2
    assert body[0].split(",")[3] == "2"
    assert len(digest) == 64
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    again = tmp_path / "again.csv"
    assert gen.write_units_csv(rows, again) == digest
