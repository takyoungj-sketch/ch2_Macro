"""Phase A-5 N-2 — 비주거 거래유형 미상: 원인 확정 + 창 밖 hash 대응률 (읽기 전용).

원인: pipeline/collective_commercial/import_refined.py INSERT_TX·rec에 deal_type/buyer_type/seller_type 칸이 없다
(molit_raw.refine_collective_molit_dataframe는 deal_type을 만든다). 2026-06-19 이전 적재본만 값이 있다.

hash = sha256(asset|source|i|price|gross_area|contract_year), i = 그 실행에서 load_collective_from_paths 결과의 행 순번.
→ 실행별 경로 목록(logs/collective_cycle_*_paths.txt, logs/_reform_collective_paths.txt)을 같은 순서로 다시 읽어 재현한다.
"""
from __future__ import annotations

import hashlib
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

from _db import OUT, ROOT, engine, md_table

sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "pipeline" / "collective_commercial"))
from collective_commercial.molit_raw import load_collective_from_paths  # noqa: E402

MAIN_LOGS = Path(r"D:\ch2\ch2_Macro\logs")
RUNS = {
    "2026-07-02": MAIN_LOGS / "_reform_collective_paths.txt",
    "2026-07-03": MAIN_LOGS / "collective_cycle_202607_paths.txt",
    "2026-08-08": MAIN_LOGS / "collective_cycle_202608_paths.txt",
    "2026-09-02": MAIN_LOGS / "collective_cycle_202609_paths.txt",
    "2026-10-02": MAIN_LOGS / "collective_cycle_202610_paths.txt",
    "2026-11-03": MAIN_LOGS / "collective_cycle_202611_paths.txt",
}
t0 = time.time()


def remap(line: str) -> Path:
    s = line.strip()
    s = s.replace("C:\\ch2\\ch2_Macro\\raw\\인천 행정구역", "D:\\ch2\\ch2_Macro\\raw\\인천, 전남광주\\인천 행정구역")
    s = s.replace("C:\\ch2\\ch2_Macro\\raw\\전남광주 행정구역", "D:\\ch2\\ch2_Macro\\raw\\인천, 전남광주\\전남광주 행정구역")
    s = s.replace("C:\\ch2\\", "D:\\ch2\\").replace("E:\\ch2\\", "D:\\ch2\\")
    return Path(s)


def main():
    table: dict[str, tuple[str, str]] = {}
    run_rows = []
    for run, pf in RUNS.items():
        lines = [ln for ln in pf.read_text(encoding="utf-8").splitlines() if ln.strip()]
        shop = [remap(x) for x in lines if "_상업업무_" in Path(x.strip()).name]
        fac = [remap(x) for x in lines if "_공장창고_" in Path(x.strip()).name]
        missing = [p for p in shop + fac if not p.is_file()]
        for src, paths, asset in (("molit_shop_raw", shop, "collective_shop"), ("molit_factory_raw", fac, "collective_factory")):
            df = load_collective_from_paths([p for p in paths if p.is_file()], asset_type=asset)
            n = 0
            for i, row in enumerate(df.itertuples(index=False)):
                th = hashlib.sha256(f"{asset}|{src}|{i}|{row.price}|{row.gross_area}|{row.contract_year}".encode("utf-8")).hexdigest()
                table[th] = (run, row.deal_type if isinstance(row.deal_type, str) else "")
                n += 1
            run_rows.append((run, src, len(paths), len(missing), n))
        print(f"[{time.time()-t0:6.1f}s] {run} shop={len(shop)} fac={len(fac)} missing={len(missing)}", flush=True)
    with engine().connect() as c:
        db = pd.read_sql("""select transaction_hash, created_at::date::text loaded, contract_date
                            from collective_commercial_transactions
                            where deal_type is null and contract_date >= '2021-11-01'""", c)
    # 다음 cycle(2612: 2025-12~2026-11)이 다시 채우는 창
    db["window"] = (pd.to_datetime(db["contract_date"]) >= "2025-12-01").map({True: "next_cycle", False: "out_of_window"})
    hit = db["transaction_hash"].map(table)
    db["m"] = ["match" if isinstance(h, tuple) and h[0] == ld else ("match_other_run" if isinstance(h, tuple) else "no_match")
               for h, ld in zip(hit, db["loaded"])]
    db["new"] = [h[1] if isinstance(h, tuple) else "" for h in hit]
    g = db.groupby(["window", "loaded", "m"]).size().reset_index(name="n")
    g2 = db[db.m == "match"].assign(new=lambda x: x.new.replace("", "(공란)")).groupby(["window", "new"]).size().reset_index(name="n")
    L = ["# A-5 N-2 비주거 거래유형", "",
         md_table(run_rows, ["실행", "source", "경로", "없는 파일", "재현 행"]), "",
         "## 미상 행(계약 2021-11~) 대응", md_table([tuple(r) for r in g.itertuples(index=False)], ["창", "적재일", "대응", "행"]), "",
         md_table([tuple(r) for r in g2.itertuples(index=False)], ["창", "새 값", "행"])]
    (OUT / "a5_commercial_result.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
