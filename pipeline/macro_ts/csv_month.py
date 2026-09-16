"""MOLIT CSV 한 장 → 달력월 건수·만원 합. 원장 정제 없음."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import pandas as pd

CANCEL_RE = re.compile(r"^\d{4,8}$")
YM_FILE_RE = re.compile(r"_(\d{4})\.csv$", re.I)
KEEP_COL = re.compile(r"^(계약년월|계약연월|거래금액|해제사유발생일)$")
FOLDER_TO_MIX: dict[str, str] = {
    "토지": "토지",
    "상가": "상가",
    "상업업무": "상가",
    "공장": "공장",
    "공장창고": "공장",
    "단독다가구": "단독다가구",
    "아파트": "아파트",
    "오피스텔": "오피스텔",
    "연립다세대": "연립다세대",
    "분양권": "분양권",
    "분양입주권": "분양권",
}


def mix_type_from_folder(name: str) -> str | None:
    stem = name.split("_")[0]
    return FOLDER_TO_MIX.get(stem)


def file_year(path: Path) -> int | None:
    m = YM_FILE_RE.search(path.name)
    return int(m.group(1)) if m else None


def header_skiprows(path: Path) -> int:
    raw = path.read_bytes()[:16384]
    for enc in ("cp949", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("cp949", errors="replace")
    for i, line in enumerate(text.splitlines()):
        if "거래금액" in line and ("계약년월" in line or "계약연월" in line):
            return i
    return 15


def _col(df: pd.DataFrame, *names: str) -> pd.Series | None:
    stripped = {str(c).strip(): c for c in df.columns}
    for n in names:
        if n in stripped:
            return df[stripped[n]]
        for label, orig in stripped.items():
            if n in label:
                return df[orig]
    return None


def parse_ym_value(v) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().replace("-", "").replace(".", "")
    if s.endswith(".0"):
        s = s[:-2]
    if not s.isdigit():
        return None
    if len(s) == 6:
        y, m = int(s[:4]), int(s[4:])
        if 1 <= m <= 12 and y >= 1990:
            return y * 100 + m
    return None


def parse_price_value(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().replace(",", "").replace(" ", "")
    if not s or s in {"-", "nan", "None"}:
        return None
    try:
        x = float(s)
    except ValueError:
        return None
    if x <= 0:
        return None
    return x


def is_cancelled(v) -> bool:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return False
    s = str(v).strip()
    if s in {"", "-", "nan", "None"}:
        return False
    return bool(CANCEL_RE.match(s))


def aggregate_csv(path: Path) -> dict[int, list[float]]:
    """ym -> [n, amount_10k]."""
    skip = header_skiprows(path)
    last_err: Exception | None = None
    df = None
    for enc in ("cp949", "utf-8-sig"):
        try:
            df = pd.read_csv(
                path,
                encoding=enc,
                skiprows=skip,
                header=0,
                dtype=str,
                usecols=lambda c: bool(KEEP_COL.search(str(c).strip()) or "거래금액" in str(c)),
                low_memory=False,
            )
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            df = None
    if df is None:
        raise last_err or RuntimeError(f"read fail {path}")
    ym_s = _col(df, "계약년월", "계약연월")
    pr_s = _col(df, "거래금액(만원)", "거래금액")
    if ym_s is None or pr_s is None:
        return {}
    cancel_s = _col(df, "해제사유발생일")
    out: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for i in range(len(df)):
        if cancel_s is not None and is_cancelled(cancel_s.iloc[i]):
            continue
        ym = parse_ym_value(ym_s.iloc[i])
        price = parse_price_value(pr_s.iloc[i])
        if ym is None or price is None:
            continue
        cell = out[ym]
        cell[0] += 1
        cell[1] += price
    return dict(out)


def iter_source_files(repo: Path) -> Iterable[tuple[Path, str, str]]:
    """(path, mix_type, source) long_term year<=2020, base year>=2021."""
    pairs = (
        ("raw/raw long term", "long_term", 2010, 2020),
        ("raw/raw base", "base", 2021, 2099),
    )
    for rel, source, y0, y1 in pairs:
        root = repo / rel
        if not root.is_dir():
            continue
        for folder in sorted(root.iterdir()):
            if not folder.is_dir():
                continue
            mix = mix_type_from_folder(folder.name)
            if mix is None:
                continue
            for csv in folder.glob("*.csv"):
                if csv.name.startswith("."):
                    continue
                if "failed" in csv.parts:
                    continue
                y = file_year(csv)
                if y is None or y < y0 or y > y1:
                    continue
                yield csv, mix, source


def parse_job(path: str) -> tuple[str, dict[int, list[float]], str | None]:
    p = Path(path)
    try:
        return path, aggregate_csv(p), None
    except Exception as exc:  # noqa: BLE001
        return path, {}, str(exc)
