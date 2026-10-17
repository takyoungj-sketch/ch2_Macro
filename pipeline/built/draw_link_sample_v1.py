"""Plan step 4-C: stratified random sample of linked composite transactions for blind checking.

The worksheet shows only transaction-side facts (address, masked lot, road, areas, date, price),
so the checker finds the true lot without seeing ours. Our answer stays in the key file.
Both files live outside the repo; the design report holds counts only.

Strata: 일반 register × asset type × region group, 집합 register × asset type, other (tied
building / changed / missing) pooled. Rows are in random order inside each stratum, and
`확인차수` 1 is the first half, so a finished first round is itself a valid random sample.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import bindparam, text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.db_utils import get_built_engine  # noqa: E402
from built.measure_link_quality_v1 import ROWS, VERIFY  # noqa: E402

SEED = 20261018
REGION = {**{s: "수도권" for s in ("11", "28", "41")}, **{s: "광역시" for s in ("26", "27", "30", "31", "36")}}
ASSET = {"detached": "단독다가구", "commercial": "상업업무", "factory": "공장창고"}
OUT = VERIFY / "built_link_sample_v1"
TX_COLS_SQL = """
SELECT transaction_hash, addr1, addr2, addr3, addr4, addr5, lot_number, road_name, gross_area, land_area,
       contract_date, price, building_use
FROM built_transactions WHERE transaction_hash IN :hashes
"""
WORKSHEET_COLS = [
    "번호", "확인차수", "묶음", "KAIS검색힌트", "주소", "마스킹지번", "도로명", "연면적", "대지", "계약일", "가격_만원",
    "건물용도", "KAIS_실제지번", "확인불가", "메모",
]


def stratum(r) -> str:
    reg = r["register"] if r["register"] in ("일반", "집합") else "기타"
    if reg == "기타":
        return "기타(동률·변경·원장없음)"
    if reg == "집합":
        return f"집합|{ASSET[r['asset_type']]}"
    return f"일반|{ASSET[r['asset_type']]}|{REGION.get(r['sido'], '도')}"


def allocation(name: str, n_general: int, n_collective: int, n_other: int) -> int:
    if name.startswith("일반"):
        return n_general
    return n_collective if name.startswith("집합") else n_other


def tx_details(hashes: list[str]) -> pd.DataFrame:
    q = text(TX_COLS_SQL).bindparams(bindparam("hashes", expanding=True))
    with get_built_engine().connect() as conn:
        return pd.read_sql(q, conn, params={"hashes": hashes}).set_index("transaction_hash")


def hint_fields(d) -> tuple[str, str]:
    addr = " ".join(str(x) for x in (d.addr1, d.addr2, d.addr3, d.addr4, d.addr5) if pd.notna(x) and x)
    hint = " | ".join(
        str(x) for x in (
            addr, f"마스킹 {d.lot_number}", d.road_name if pd.notna(d.road_name) and d.road_name else "도로명 없음",
            f"연 {float(d.gross_area):g}", f"대지 {float(d.land_area):g}" if pd.notna(d.land_area) else "대지 없음",
            d.contract_date, f"{float(d.price):g}만원",
        )
    )
    return addr, hint


def worksheet_rows(picked: pd.DataFrame, details: pd.DataFrame, start: int) -> tuple[list[dict], list[dict]]:
    sheet, key = [], []
    for i, r in enumerate(picked.itertuples(index=False), start=start):
        d = details.loc[r.transaction_hash]
        addr, hint = hint_fields(d)
        sheet.append({
            "번호": i, "확인차수": r.round, "묶음": r.stratum, "KAIS검색힌트": hint, "주소": addr,
            "마스킹지번": d.lot_number, "도로명": d.road_name, "연면적": d.gross_area, "대지": d.land_area,
            "계약일": d.contract_date, "가격_만원": d.price, "건물용도": d.building_use,
            "KAIS_실제지번": "", "확인불가": "", "메모": "",
        })
        key.append({
            "번호": i, "transaction_hash": r.transaction_hash, "stratum": r.stratum, "round": r.round,
            "weight": r.weight, "sido": r.sido, "asset_type": r.asset_type, "register": r.register,
            "tier": r.tier, "n_exact": r.n_exact, "recovered_lot": r.parcel.split("|")[1],
            "source": getattr(r, "source", "random"),
        })
    return sheet, key


def followup_sheet(paths: list[Path]) -> dict:
    """Cases kept for re-checking (not part of the estimate). lot_a / lot_b are the competing answers."""
    fu = pd.concat([pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig") for p in paths])
    details = tx_details(fu["transaction_hash"].tolist())
    sheet, key = [], []
    for i, r in enumerate(fu.itertuples(index=False), start=1):
        d = details.loc[r.transaction_hash]
        addr, hint = hint_fields(d)
        sheet.append({
            "번호": f"F{i}", "확인차수": "후속", "묶음": r.source, "KAIS검색힌트": hint,
            "주소": addr, "마스킹지번": d.lot_number, "도로명": d.road_name, "연면적": d.gross_area, "대지": d.land_area,
            "계약일": d.contract_date, "가격_만원": d.price, "건물용도": d.building_use,
            "KAIS_실제지번": "", "확인불가": "", "메모": "",
        })
        key.append({"번호": f"F{i}", "transaction_hash": r.transaction_hash, "sido": r.sido, "source": r.source,
                    "detail": r.detail, "lot_a": r.lot_a, "lot_b": r.lot_b})
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(sheet, columns=WORKSHEET_COLS).to_csv(OUT / "followup_worksheet.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(key).to_csv(OUT / "followup_key.csv", index=False, encoding="utf-8-sig")
    return {k: int(v) for k, v in fu.groupby(["source", "detail"]).size().items()} | {"total": int(len(fu))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n-general", type=int, default=20)
    ap.add_argument("--n-collective", type=int, default=10)
    ap.add_argument("--n-other", type=int, default=10)
    ap.add_argument("--followup", type=Path, nargs="*", default=[])
    args = ap.parse_args()
    df = pd.read_pickle(ROWS)
    linked = df[df["tier"].notna()].copy()
    linked["stratum"] = linked.apply(stratum, axis=1)
    rng = random.Random(SEED)
    parts, design = [], {}
    for name, g in sorted(linked.groupby("stratum"), key=lambda x: x[0]):
        n = min(len(g), allocation(name, args.n_general, args.n_collective, args.n_other))
        idx = sorted(g.index)
        rng.shuffle(idx)
        pick = g.loc[idx[:n]].copy()
        pick["round"] = [1 if j < (n + 1) // 2 else 2 for j in range(n)]
        pick["weight"] = len(g) / n
        parts.append(pick)
        design[name] = {"population": int(len(g)), "sample": int(n)}
    picked = pd.concat(parts)
    details = tx_details(picked["transaction_hash"].tolist())
    sheet, key = worksheet_rows(picked, details, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(sheet, columns=WORKSHEET_COLS).to_csv(OUT / "worksheet.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(key).to_csv(OUT / "key.csv", index=False, encoding="utf-8-sig")
    report = {
        "seed": SEED,
        "population_linked": int(len(linked)),
        "sample": int(len(picked)),
        "round1": int((picked["round"] == 1).sum()),
        "strata": design,
        "worksheet": str(OUT / "worksheet.csv"),
        "note": "blind: worksheet has no recovered lot; key.csv stays local",
    }
    if args.followup:
        report["followup"] = {str(k): v for k, v in followup_sheet(args.followup).items()}
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
