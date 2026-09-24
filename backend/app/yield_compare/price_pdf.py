"""부동산원 전국 매매가격지수 PDF. 12월 지수만 쓴다."""

from __future__ import annotations

import re
import zlib
from pathlib import Path

_TM_TJ = re.compile(
    r"/F(\d+)\s+[0-9.]+\s+Tf\n.*?([0-9.\-]+)\s+([0-9.\-]+)\s+Tm\n\[(.*?)\]TJ",
    re.S,
)
_HEX = re.compile(r"<([0-9A-Fa-f]+)>")
_BFCHAR = re.compile(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")
_BFRANGE = re.compile(
    r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>"
)


def _utf16(hex_dst: str) -> str:
    if hex_dst.lower() == "ffff" or not hex_dst:
        return ""
    raw = bytes.fromhex(hex_dst)
    if len(raw) % 2:
        return ""
    return raw.decode("utf-16-be", errors="ignore")


def _cmaps(data: bytes) -> dict[str, dict[str, str]]:
    """내용에 bfrange가 있으면 표 글꼴(F2), 없으면 머리글(F1)."""
    found: list[dict[str, str]] = []
    table: dict[str, str] | None = None
    header: dict[str, str] | None = None
    for match in re.finditer(rb"stream\r?\n", data):
        start = match.end()
        end = data.find(b"endstream", start)
        chunk = data[start:end]
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]
        elif chunk.endswith(b"\n"):
            chunk = chunk[:-1]
        try:
            text = zlib.decompress(chunk)
        except zlib.error:
            continue
        if b"beginbfchar" not in text:
            continue
        body = text.decode("latin1")
        mapping: dict[str, str] = {}
        char_part = body.split("beginbfrange")[0]
        for src, dst in _BFCHAR.findall(char_part):
            ch = _utf16(dst)
            if ch:
                mapping[src.lower().zfill(4)] = ch
        is_table = b"beginbfrange" in text
        if is_table:
            range_part = body.split("beginbfrange", 1)[1]
            for a, b, dst in _BFRANGE.findall(range_part):
                start_id = int(a, 16)
                end_id = int(b, 16)
                code = int(dst, 16)
                for i, cid in enumerate(range(start_id, end_id + 1)):
                    mapping[f"{cid:04x}"] = chr(code + i)
            table = mapping
        else:
            header = mapping
        found.append(mapping)
    out: dict[str, dict[str, str]] = {}
    if header:
        out["1"] = header
    if table:
        out["2"] = table
    if not out and found:
        out["2"] = found[-1]
    return out


def _content(data: bytes) -> str:
    for match in re.finditer(rb"stream\r?\n", data):
        start = match.end()
        end = data.find(b"endstream", start)
        chunk = data[start:end]
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]
        elif chunk.endswith(b"\n"):
            chunk = chunk[:-1]
        try:
            text = zlib.decompress(chunk)
        except zlib.error:
            continue
        if b"]TJ" in text:
            return text.decode("latin1")
    raise ValueError("PDF 텍스트 스트림 없음")


def _decode(hex_body: str, cmap: dict[str, str]) -> str:
    chars: list[str] = []
    for blob in _HEX.findall(hex_body):
        for i in range(0, len(blob), 4):
            chars.append(cmap.get(blob[i : i + 4].lower(), ""))
    return "".join(chars)


def december_index(path: Path) -> dict[int, float]:
    """연도 → 12월 지수. 12월이 없는 해(진행 중)는 빠진다."""
    data = path.read_bytes()
    cmaps = _cmaps(data)
    table = cmaps.get("2") or {}
    if not table:
        raise ValueError(f"표 글꼴 없음: {path.name}")
    rows: dict[float, list[tuple[float, str]]] = {}
    font = "1"
    for font_id, x, y, body in _TM_TJ.findall(_content(data)):
        font = font_id
        if font != "2":
            continue
        text = _decode(body, table).strip()
        if not text:
            continue
        rows.setdefault(round(float(y), 1), []).append((float(x), text))
    out: dict[int, float] = {}
    for cells in rows.values():
        ordered = [t for _, t in sorted(cells)]
        if not ordered or not re.fullmatch(r"20\d{2}", ordered[0]):
            continue
        months = []
        for token in ordered[1:]:
            try:
                months.append(float(token.replace(",", "")))
            except ValueError:
                continue
        if len(months) < 12:
            continue
        out[int(ordered[0])] = months[11]
    if not out:
        raise ValueError(f"12월 지수 없음: {path.name}")
    return out


def december_return_pct(index: dict[int, float], year: int) -> float | None:
    """그해 12월 / 전년 12월 − 1, 퍼센트. 연평균 지수는 쓰지 않는다."""
    cur = index.get(year)
    prev = index.get(year - 1)
    if cur is None or prev is None or prev == 0:
        return None
    return (cur / prev - 1.0) * 100.0
