# -*- coding: utf-8 -*-
"""검토된 완료만 운영 속성 표의 빈칸에 넣는다.

주차는 총대수와 세대당 주차가 둘 다 비어 있을 때만.
시공사는 builder_raw가 비어 있을 때만. 기업집단과 정규화는 쓰지 않는다.
보류·대기·속성 행이 없는 단지는 건너뛴다.
"""
from __future__ import annotations

import csv
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import text

from app.collective.db import get_collective_engine

FILL = ROOT / "docs" / "lab" / "naver_complex_fill"
FILES = [
    FILL / "1단계_명단.csv",
    FILL / "2단계_명단.csv",
    FILL / "3단계_명단.csv",
]
Q = Decimal("0.001")
BUILDER_MAX = 200


def num(raw):
    if raw is None or raw == "":
        return None
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    s = str(raw).strip().replace(",", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def load_done():
    out = {}
    for path in FILES:
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("상태") != "완료":
                    continue
                key = (row.get("building_key") or "").strip()
                if not key:
                    continue
                park = num(row.get("KB_주차대수"))
                if park is not None and park == park.to_integral_value() and park >= 0:
                    park_i = int(park)
                else:
                    park_i = None
                builder = (row.get("KB_시공사") or "").strip()
                if len(builder) > BUILDER_MAX:
                    builder = ""
                out[key] = {
                    "park": park_i,
                    "per": num(row.get("KB_세대당주차")),
                    "hh": num(row.get("세대수")),
                    "kbhh": num(row.get("KB_세대수")),
                    "builder": builder,
                }
    return out


def ratio(park, *households):
    for hh in households:
        if hh is not None and hh > 0:
            return (Decimal(park) / hh).quantize(Q, rounding=ROUND_HALF_UP)
    return None


def with_flag(raw, *codes):
    parts = [p.strip() for p in str(raw or "").split(",") if p.strip()]
    for code in codes:
        if code and code not in parts:
            parts.append(code)
    return ",".join(parts)


def main():
    done = load_done()
    eng = get_collective_engine()
    if eng is None:
        raise SystemExit("collective database is not configured")
    keys = list(done)
    found = {}
    with eng.connect() as conn:
        for i in range(0, len(keys), 400):
            recs = conn.execute(
                text(
                    """
                    SELECT building_key, parking_total, parking_per_household,
                           households, builder_raw, attr_quality_flags
                    FROM collective_building_attributes
                    WHERE asset_type = 'apartment'
                      AND snapshot_ym = '202607'
                      AND building_key = ANY(:keys)
                    """
                ),
                {"keys": keys[i : i + 400]},
            ).mappings().all()
            for rec in recs:
                found[rec["building_key"]] = rec

    parking_rows = []
    builder_rows = []
    skip = {"no_row": 0, "builder_kept": 0, "builder_blank": 0, "park_kept": 0, "no_ratio": 0}
    for key, item in done.items():
        rec = found.get(key)
        if rec is None:
            skip["no_row"] += 1
            continue
        flags = rec["attr_quality_flags"]
        if item["park"] is not None and rec["parking_total"] is None and rec["parking_per_household"] is None:
            per = item["per"]
            if per is not None and per > 0:
                per = per.quantize(Q, rounding=ROUND_HALF_UP)
            elif item["park"] > 0:
                per = ratio(item["park"], num(rec["households"]), item["hh"], item["kbhh"])
            elif item["park"] == 0:
                per = Decimal("0.000")
            else:
                per = None
            if per is None:
                skip["no_ratio"] += 1
            else:
                extra = ["kb_internet_parking"]
                if per > 5:
                    extra.append("parking_implausible")
                flags = with_flag(flags, *extra)
                parking_rows.append({"bk": key, "pt": item["park"], "pp": per, "flags": flags})
        elif item["park"] is not None:
            skip["park_kept"] += 1

        raw = (rec["builder_raw"] or "").strip()
        if item["builder"] and not raw:
            flags = with_flag(flags, "kb_internet_builder")
            builder_rows.append({"bk": key, "builder": item["builder"], "flags": flags})
        elif raw:
            skip["builder_kept"] += 1
        else:
            skip["builder_blank"] += 1

    # 같은 행을 주차와 시공사가 같이 고치면 플래그가 마지막 쓰기로 남게 합친다.
    by_key = {}
    for row in parking_rows:
        by_key[row["bk"]] = {"bk": row["bk"], "pt": row["pt"], "pp": row["pp"], "flags": row["flags"], "builder": None}
    for row in builder_rows:
        slot = by_key.get(row["bk"])
        if slot is None:
            by_key[row["bk"]] = {
                "bk": row["bk"],
                "pt": None,
                "pp": None,
                "flags": row["flags"],
                "builder": row["builder"],
            }
        else:
            slot["builder"] = row["builder"]
            slot["flags"] = with_flag(row["flags"], "kb_internet_parking", "parking_implausible" if "parking_implausible" in slot["flags"] else "")

    park_sql = text(
        """
        UPDATE collective_building_attributes
        SET parking_total = :pt,
            parking_per_household = :pp,
            attr_quality_flags = :flags
        WHERE asset_type = 'apartment'
          AND snapshot_ym = '202607'
          AND building_key = :bk
          AND parking_total IS NULL
          AND parking_per_household IS NULL
        """
    )
    both_sql = text(
        """
        UPDATE collective_building_attributes
        SET parking_total = :pt,
            parking_per_household = :pp,
            builder_raw = :builder,
            attr_quality_flags = :flags
        WHERE asset_type = 'apartment'
          AND snapshot_ym = '202607'
          AND building_key = :bk
          AND parking_total IS NULL
          AND parking_per_household IS NULL
          AND (builder_raw IS NULL OR btrim(builder_raw) = '')
        """
    )
    builder_sql = text(
        """
        UPDATE collective_building_attributes
        SET builder_raw = :builder,
            attr_quality_flags = :flags
        WHERE asset_type = 'apartment'
          AND snapshot_ym = '202607'
          AND building_key = :bk
          AND (builder_raw IS NULL OR btrim(builder_raw) = '')
        """
    )
    park_n = both_n = builder_n = 0
    with eng.begin() as conn:
        for row in by_key.values():
            if row["pt"] is not None and row["builder"]:
                result = conn.execute(both_sql, row)
                both_n += result.rowcount or 0
            elif row["pt"] is not None:
                result = conn.execute(park_sql, row)
                park_n += result.rowcount or 0
            elif row["builder"]:
                result = conn.execute(builder_sql, row)
                builder_n += result.rowcount or 0
        flagged_builder = conn.execute(
            text(
                """
                SELECT count(*) FROM collective_building_attributes
                WHERE asset_type = 'apartment' AND snapshot_ym = '202607'
                  AND attr_quality_flags LIKE '%kb_internet_builder%'
                """
            )
        ).scalar()
        flagged_park = conn.execute(
            text(
                """
                SELECT count(*) FROM collective_building_attributes
                WHERE asset_type = 'apartment' AND snapshot_ym = '202607'
                  AND attr_quality_flags LIKE '%kb_internet_parking%'
                """
            )
        ).scalar()
    print(
        f"done_keys {len(done)} no_row {skip['no_row']} "
        f"parking_only {park_n} builder_only {builder_n} both {both_n} "
        f"builder_kept {skip['builder_kept']} builder_blank {skip['builder_blank']} "
        f"flag_builder {int(flagged_builder)} flag_parking {int(flagged_park)}"
    )


if __name__ == "__main__":
    main()
