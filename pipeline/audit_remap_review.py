"""needs_review 행을 현재 매핑 로직으로 재시도했을 때 성공 비율 추정."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from clean import build_region_lookup, map_beopjungri_codes
from db_utils import get_engine


def main() -> None:
    eng = get_engine()
    lookup = build_region_lookup(eng)

    with eng.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT lt.id,
                       COALESCE(r.raw_data->>'sigungu_name', '') AS sigungu_name,
                       COALESCE(r.raw_data->>'eupmyeondong_name', '') AS eupmyeondong_name,
                       COALESCE(r.raw_data->>'sigungu_code', '') AS sigungu_code,
                       COALESCE(r.raw_data->>'sido_code', '') AS sido_code,
                       lt.mapping_notes
                FROM land_transactions lt
                JOIN land_transactions_raw r ON r.id = lt.raw_id
                WHERE lt.needs_review = TRUE
                """
            )
        ).fetchall()

    df = pd.DataFrame(
        rows,
        columns=[
            "id",
            "sigungu_name",
            "eupmyeondong_name",
            "sigungu_code",
            "sido_code",
            "mapping_notes",
        ],
    )
    total = len(df)
    meta = map_beopjungri_codes(df, lookup)
    ok = meta["beopjungri_code"].fillna("").astype(str).str.strip().ne("")
    n_ok = int(ok.sum())
    print(f"needs_review_total={total:,}")
    print(f"would_map_now={n_ok:,} ({100.0 * n_ok / total:.2f}%)")
    print(f"still_fail={total - n_ok:,}")

    for note in ("no_strong_match", "no_strong_match_short_address"):
        sub = df["mapping_notes"] == note
        if sub.any():
            n = int(ok[sub].sum())
            t = int(sub.sum())
            print(f"  {note}: would_map {n:,}/{t:,} ({100.0 * n / t:.2f}%)")


if __name__ == "__main__":
    main()
