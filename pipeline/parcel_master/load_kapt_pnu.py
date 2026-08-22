"""K-apt 단지_필지고유번호 → collective_stats.builder_master.pnu

  python -m parcel_master.load_kapt_pnu
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from parcel_master.db_utils import get_collective_engine
from parcel_master.paths import kapt_pnu_xlsx

DDL = Path(__file__).resolve().parents[2] / "db" / "065_builder_master_pnu.sql"


def load_pnu_map(path: Path | None = None) -> pd.DataFrame:
    src = path or kapt_pnu_xlsx()
    df = pd.read_excel(src, skiprows=1, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    pnu_col = next(c for c in df.columns if "고유" in c or c == "고유번호")
    danji_col = next(c for c in df.columns if "단지" in c or "kapt" in c.lower())
    out = df[[pnu_col, danji_col]].rename(columns={pnu_col: "pnu", danji_col: "danji_code"})
    out["pnu"] = out["pnu"].astype(str).str.strip()
    out["danji_code"] = out["danji_code"].astype(str).str.strip()
    out = out[(out["pnu"].str.len() == 19) & out["pnu"].str.isdigit() & (out["danji_code"] != "")]
    return out.drop_duplicates("danji_code")


def apply_ddl(engine) -> None:
    raw = DDL.read_text(encoding="utf-8")
    with engine.begin() as conn:
        for stmt in raw.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))


def main() -> None:
    engine = get_collective_engine()
    apply_ddl(engine)
    mapping = load_pnu_map()
    print(f"K-apt PNU rows={len(mapping):,} unique_pnu={mapping['pnu'].nunique():,}", flush=True)
    sql = text("UPDATE builder_master SET pnu = :pnu WHERE danji_code = :danji_code")
    updated = 0
    with engine.begin() as conn:
        for rec in mapping.itertuples(index=False):
            result = conn.execute(sql, {"pnu": rec.pnu, "danji_code": rec.danji_code})
            updated += result.rowcount or 0
    with engine.connect() as conn:
        filled = conn.execute(text("SELECT COUNT(*) FROM builder_master WHERE pnu IS NOT NULL")).scalar()
        total = conn.execute(text("SELECT COUNT(*) FROM builder_master")).scalar()
        shared = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM (
                    SELECT pnu FROM builder_master
                    WHERE pnu IS NOT NULL
                    GROUP BY pnu HAVING COUNT(*) > 1
                ) s
                """
            )
        ).scalar()
    print(
        f"builder_master pnu filled={filled}/{total}  row_updates={updated}  shared_pnu={shared}",
        flush=True,
    )


if __name__ == "__main__":
    main()
