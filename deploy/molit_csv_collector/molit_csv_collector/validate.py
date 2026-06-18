"""MOLIT CSV 메타데이터 검증."""

from __future__ import annotations

import re
from pathlib import Path


def decode_csv_text(path: Path, *, max_bytes: int = 65536) -> str:
    raw = path.read_bytes()[:max_bytes]
    for enc in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp949", errors="replace")


def parse_csv_metadata(path: Path) -> dict[str, str]:
    text = decode_csv_text(path)
    meta: dict[str, str] = {}
    for line in text.splitlines()[:20]:
        line = line.strip().strip('"')
        if line.startswith("계약일자"):
            meta["date_range"] = line.split(":", 1)[-1].strip()
        elif line.startswith("시도"):
            meta["region"] = line.split(":", 1)[-1].strip()
        elif line.startswith("실거래구분"):
            meta["deal_type"] = line.split(":", 1)[-1].strip()
    return meta


def validate_csv_metadata(
    path: Path,
    *,
    region: str,
    year: int,
    type_label_ko: str,
) -> tuple[bool, str]:
    if not path.is_file() or path.stat().st_size < 100:
        return False, "파일이 비어 있거나 너무 작음"

    meta = parse_csv_metadata(path)
    if not meta.get("region"):
        return False, "CSV 메타데이터(시도) 없음"
    if not meta.get("date_range"):
        return False, "CSV 메타데이터(계약일자) 없음"

    if meta["region"].strip() != region.strip():
        return False, f"시도 불일치: 파일={meta['region']!r} 기대={region!r}"

    m = re.search(r"(\d{4})-01-01\s*~\s*(\d{4})-12-31", meta["date_range"])
    if not m:
        return False, f"계약일자 형식 이상: {meta['date_range']!r}"
    start_y, end_y = int(m.group(1)), int(m.group(2))
    if start_y != year or end_y != year:
        return False, f"연도 불일치: 파일={start_y}~{end_y} 기대={year}"

    deal = meta.get("deal_type", "")
    if type_label_ko not in deal:
        return False, f"유형 불일치: 파일={deal!r} 기대={type_label_ko!r}"

    return True, "ok"
