"""국토부 CSV 메타데이터 검증 — 잘못된 rename·race condition 방어."""

from __future__ import annotations

import re
from pathlib import Path

_ENCODINGS = ("cp949", "utf-8-sig", "utf-8")


def read_csv_text(path: Path, *, max_bytes: int = 512_000) -> str:
    raw = path.read_bytes()[:max_bytes]
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp949", errors="replace")


def parse_metadata(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines()[:20]:
        line = line.strip().strip('"')
        if " : " in line:
            key, val = line.split(" : ", 1)
            out[key.strip()] = val.strip()
    return out


def _year_from_contract_range(meta: dict[str, str]) -> tuple[int | None, int | None]:
    raw = meta.get("계약일자", "")
    m = re.search(r"(\d{4})-\d{2}-\d{2}\s*~\s*(\d{4})-\d{2}-\d{2}", raw)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def validate_csv_file(
    path: Path,
    *,
    region: str,
    year: int,
    type_label_ko: str,
    deal_type: str = "매매",
) -> tuple[bool, str]:
    if not path.is_file() or path.stat().st_size < 200:
        return False, "파일 없음 또는 크기 너무 작음"

    try:
        text = read_csv_text(path)
    except OSError as exc:
        return False, f"읽기 실패: {exc}"

    meta = parse_metadata(text)
    if not meta:
        return False, "메타데이터(검색조건) 없음 — CSV 형식 아님"

    sido = meta.get("시도", "")
    if sido != region:
        return False, f"시도 불일치: 기대={region}, 실제={sido}"

    y0, y1 = _year_from_contract_range(meta)
    if y0 is None or y1 is None:
        return False, f"계약일자 파싱 실패: {meta.get('계약일자', '')}"
    if y0 != year or y1 != year:
        return False, f"연도 불일치: 기대={year}, 실제={y0}~{y1}"

    deal = meta.get("실거래구분", "")
    if type_label_ko not in deal:
        return False, f"유형 불일치: 기대≈{type_label_ko}({deal_type}), 실제={deal}"

    return True, "ok"
