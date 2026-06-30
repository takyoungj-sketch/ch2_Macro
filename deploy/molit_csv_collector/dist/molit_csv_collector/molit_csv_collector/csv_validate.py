"""국토부 CSV 메타데이터 검증 — 잘못된 rename·race condition 방어."""

from __future__ import annotations

import re
from pathlib import Path

from .config import PropertyType

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


def _contract_range(meta: dict[str, str]) -> tuple[str | None, str | None]:
    raw = meta.get("계약일자", "")
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})", raw)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def validate_csv_file(
    path: Path,
    *,
    region: str,
    from_date: str,
    to_date: str,
    property_type: PropertyType,
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

    c0, c1 = _contract_range(meta)
    if c0 is None or c1 is None:
        return False, f"계약일자 파싱 실패: {meta.get('계약일자', '')}"
    if c0 != from_date or c1 != to_date:
        return False, f"계약일자 불일치: 기대={from_date}~{to_date}, 실제={c0}~{c1}"

    deal = meta.get("실거래구분", "")
    expected_deal = f"{property_type.label_ko}({property_type.deal_type})"
    if expected_deal not in deal.replace(" ", ""):
        if property_type.label_ko not in deal:
            return False, f"유형 불일치: 기대≈{expected_deal}, 실제={deal}"

    return True, "ok"
