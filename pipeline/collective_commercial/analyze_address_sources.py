"""집합상가 주소·도로명 확보율: 정제 vs GUKTO 원본 (샘플)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

GUKTO = Path(r"C:\startcoding\GUKTO")
OUT = Path(__file__).resolve().parent / "address_source_report.json"


def _empty_rate(s: pd.Series) -> float:
    t = s.astype(str).str.strip()
    mask = s.isna() | t.eq("") | t.eq("nan") | t.eq("-") | t.eq("None")
    return float(mask.mean())


def analyze_refined() -> dict:
    path = next(
        p
        for p in GUKTO.rglob("*.xlsx")
        if "집합상" in p.name and "정제" in str(p) and not p.name.startswith("~$")
    )
    df = pd.read_excel(path)
    cols = list(df.columns)
    # parse year
    yraw = df.get("거래연도")
    years = pd.to_numeric(yraw.astype(str).str.extract(r"(\d{2,4})")[0], errors="coerce")
    years = years.where(years >= 1900, years + 2000)

    addr_cols = [c for c in cols if str(c).startswith("주") or c in ("번지", "도로", "도로명", "도로명주소", "상세주소")]
    by_year: dict[str, dict] = {}
    for yr in sorted(y for y in years.dropna().unique()):
        sub = df[years == yr]
        row: dict = {"n": int(len(sub))}
        for c in addr_cols:
            row[c] = round(_empty_rate(sub[c]) * 100, 1)
        by_year[str(int(yr))] = row

    overall = {"n": int(len(df)), "columns": cols}
    for c in addr_cols:
        overall[c] = round(_empty_rate(df[c]) * 100, 1)

    return {"path": str(path), "overall": overall, "by_year": by_year}


def _read_raw_sample(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, skiprows=16)
    # col index 2 = 유형 (집합/일반) per prior notes
    if raw.shape[1] < 3:
        return raw.iloc[0:0]
    type_col = raw.columns[2]
    sub = raw[raw[type_col].astype(str).str.strip() == "집합"].copy()
    return sub


def analyze_raw_samples() -> dict:
    samples = []
    # one sido, all years
    sido_dir = GUKTO / "상업업무용_매매" / "충청북도"
    if not sido_dir.is_dir():
        # fallback: first sido folder
        base = GUKTO / "상업업무용_매매"
        sido_dir = next(d for d in base.iterdir() if d.is_dir())

    for year in (2021, 2022, 2023, 2024, 2025):
        matches = list(sido_dir.glob(f"*{year}.xlsx"))
        if not matches:
            continue
        path = matches[0]
        sub = _read_raw_sample(path)
        cols = [str(c) for c in sub.columns]
        # heuristic: find road / address columns by keyword
        road_cols = [c for c in cols if any(k in c for k in ("도로", "주소", "번지", "지번", "상세"))]
        addr_like = [c for c in cols if c.startswith("Unnamed") is False][:25]
        row = {
            "path": path.name,
            "year": year,
            "n_collective": int(len(sub)),
            "columns_head": addr_like,
            "road_related_cols": road_cols,
        }
        for c in road_cols[:8]:
            if c in sub.columns:
                row[f"empty_{c}"] = round(_empty_rate(sub[c]) * 100, 1)
                vals = sub[c].dropna().astype(str).str.strip()
                vals = vals[~vals.isin(("", "nan", "-"))]
                row[f"sample_{c}"] = vals.head(3).tolist()
        samples.append(row)

    return {"sido": sido_dir.name, "samples": samples}


def main() -> None:
    report = {
        "refined": analyze_refined(),
        "raw_sample": analyze_raw_samples(),
        "notes": [
            "정제 파일에 도로명 컬럼 없으면 cluster_key 도로명 설계 불가",
            "원본 skiprows=16, col2=유형(집합) 필터",
        ],
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
