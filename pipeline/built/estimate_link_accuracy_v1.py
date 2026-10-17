"""Plan step 4-C: link accuracy from the blind sample once `KAIS_실제지번` is filled.

correct = the checker's lot equals our recovered lot ("동일" also counts). Rows marked
`확인불가` are excluded and counted. Estimates are stratum-weighted with a normal
approximation on the stratified variance; per-stratum Wilson intervals are given too.
Counts only; nothing is written to any DB.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from built.draw_link_sample_v1 import OUT  # noqa: E402

LOT_RE = re.compile(r"(산\s*)?(\d+)(?:\s*-\s*(\d+))?")


def norm_lot(s: str) -> str | None:
    m = LOT_RE.search(str(s or ""))
    if not m:
        return None
    return f"{'산' if m.group(1) else ''}{int(m.group(2))}" + (f"-{int(m.group(3))}" if m.group(3) and int(m.group(3)) else "")


def wilson(k: int, n: int) -> list[float] | None:
    if n == 0:
        return None
    p, z = k / n, 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def combine(cells: pd.DataFrame) -> dict:
    """cells: stratum, N (population), n (checked), k (correct)."""
    cells = cells[cells["n"] > 0]
    if cells.empty:
        return {"checked": 0}
    total = cells["N"].sum()
    p = (cells["N"] * cells["k"] / cells["n"]).sum() / total
    var = 0.0
    for r in cells.itertuples(index=False):
        ph = r.k / r.n
        fpc = 1 - r.n / r.N if r.N else 0
        var += (r.N / total) ** 2 * fpc * ph * (1 - ph) / max(r.n - 1, 1)
    se = math.sqrt(var)
    return {
        "checked": int(cells["n"].sum()), "correct": int(cells["k"].sum()), "strata": int(len(cells)),
        "estimate": round(p, 4), "ci95": [round(max(0, p - 1.96 * se), 4), round(min(1, p + 1.96 * se), 4)],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--design", type=Path, required=True, help="draw_link_sample_v1 report (populations)")
    args = ap.parse_args()
    sheet = pd.read_csv(OUT / "worksheet.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    key = pd.read_csv(OUT / "key.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    design = json.loads(args.design.read_text(encoding="utf-8"))["strata"]
    m = key.merge(sheet[["번호", "KAIS_실제지번", "확인불가"]], on="번호")
    m = m[m["source"] == "random"]
    unable = m["확인불가"].str.strip() != ""
    done = m[(m["KAIS_실제지번"].str.strip() != "") & ~unable].copy()
    done["correct"] = [
        a.strip() == "동일" or norm_lot(a) == norm_lot(b) for a, b in zip(done["KAIS_실제지번"], done["recovered_lot"])
    ]
    done["residential"] = done["asset_type"].map({"detached": "주거"}).fillna("비주거")
    done["register_group"] = done["stratum"].str.split("|").str[0]
    done["region"] = done["stratum"].map(lambda s: s.split("|")[2] if s.count("|") == 2 else None)
    cells = done.groupby("stratum").agg(n=("correct", "size"), k=("correct", "sum")).reset_index()
    cells["N"] = cells["stratum"].map(lambda s: design[s]["population"])
    meta = done.drop_duplicates("stratum").set_index("stratum")[["residential", "register_group", "region"]]
    cells = cells.join(meta, on="stratum")
    report = {
        "sample_rows": int(len(m)), "checked": int(len(done)), "unable": int(unable.sum()),
        "pending": int(len(m) - len(done) - unable.sum()),
        "national": combine(cells),
        "by_residential": {k: combine(g) for k, g in cells.groupby("residential")},
        "by_register": {k: combine(g) for k, g in cells.groupby("register_group")},
        "by_region_general": {k: combine(g) for k, g in cells.dropna(subset=["region"]).groupby("region")},
        "by_stratum": {
            r.stratum: {"population": int(r.N), "checked": int(r.n), "correct": int(r.k), "wilson95": wilson(int(r.k), int(r.n))}
            for r in cells.itertuples(index=False)
        },
        "note": "independent sample accuracy; regions below the province level are not estimated",
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
