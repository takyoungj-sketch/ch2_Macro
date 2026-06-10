"""
세종특별자치시 「시도 + 행정동」(2토큰) 주소 재매핑.

배경:
- clean.py Fallback 3(sejong_admin_leaf) 적용 전 적재분은 beopjungri_code 공백·sido_code 오류로 남음.
- raw.sigungu_name 이 `세종특별자치시  ○○동` 형태인 거래만 대상.

실행:
  py pipeline/remap_sejong_admin_leaf.py --dry-run
  py pipeline/remap_sejong_admin_leaf.py --as-of 2026-05-01 --windows 3,5
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

_PIPELINE = Path(__file__).resolve().parent
if str(_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_PIPELINE))

from clean import build_region_lookup, map_beopjungri_codes  # noqa: E402
from transaction_hash import hash_from_series  # noqa: E402

_SEJONG_DONG_RAW_SQL = """
    SELECT lt.id AS lt_id,
           lt.raw_id,
           btrim(lt.beopjungri_code::text) AS old_code,
           COALESCE(lt.needs_review, FALSE) AS old_review,
           COALESCE(lt.mapping_notes, '') AS old_notes,
           r.raw_data->>'sigungu_name' AS sigungu_name,
           r.raw_data->>'eupmyeondong_name' AS eupmyeondong_name,
           r.raw_data->>'sigungu_code' AS sigungu_code,
           r.raw_data->>'sido_code' AS sido_code
    FROM land_transactions lt
    JOIN land_transactions_raw r ON r.id = lt.raw_id
    WHERE r.raw_data->>'sigungu_name' ~ '^세종특별자치시\\s+[가-힣]+동\\s*$'
"""


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _select_targets(engine) -> pd.DataFrame:
    with engine.connect() as c:
        return pd.read_sql(text(_SEJONG_DONG_RAW_SQL), c)


def _apply_updates(engine, df: pd.DataFrame, mapped: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    work = df.copy()
    work["new_code"] = mapped["beopjungri_code"].astype(str).str.strip()
    work["new_review"] = mapped["needs_review"].astype(bool)
    work["new_notes"] = mapped["mapping_notes"].astype(str)
    work["old_code"] = work["old_code"].fillna("").astype(str).str.strip()
    work["old_notes"] = work["old_notes"].fillna("").astype(str)

    changed = work[
        (work["new_code"] != work["old_code"])
        | (work["new_review"] != work["old_review"].astype(bool))
        | (work["new_notes"] != work["old_notes"])
    ]
    if changed.empty:
        return 0, len(work)

    rows = []
    for r in changed.itertuples(index=False):
        bc = str(r.new_code).strip()
        row = {
            "lt_id": int(r.lt_id),
            "bc": bc if bc else None,
            "sd": bc[:2] if len(bc) >= 2 else "36",
            "sg": bc[:5] if len(bc) >= 5 else "36110",
            "rv": bool(r.new_review),
            "nt": str(r.new_notes) if str(r.new_notes) else None,
            "valid": bool(bc),
        }
        rows.append(row)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE land_transactions
                SET beopjungri_code = :bc,
                    sido_code = :sd,
                    sigungu_code = :sg,
                    needs_review = :rv,
                    mapping_notes = :nt,
                    is_valid = :valid,
                    updated_at = NOW()
                WHERE id = :lt_id
                """
            ),
            rows,
        )

    # transaction_hash 갱신 — 충돌 시 중복 행(공백 beop 적재분) 삭제
    with engine.connect() as c:
        ids = [int(x["lt_id"]) for x in rows]
        lt = pd.read_sql(
            text("SELECT * FROM land_transactions WHERE id = ANY(:ids)"),
            c,
            params={"ids": ids},
        )

    deleted = 0
    updated = 0
    with engine.begin() as conn:
        for _, row in lt.iterrows():
            lt_id = int(row["id"])
            new_h = hash_from_series(row)
            conflict = conn.execute(
                text(
                    """
                    SELECT id FROM land_transactions
                    WHERE transaction_hash = :th AND id <> :id
                    LIMIT 1
                    """
                ),
                {"th": new_h, "id": lt_id},
            ).fetchone()
            if conflict:
                conn.execute(
                    text("DELETE FROM land_transactions WHERE id = :id"),
                    {"id": lt_id},
                )
                deleted += 1
            else:
                conn.execute(
                    text(
                        """
                        UPDATE land_transactions
                        SET transaction_hash = :th, updated_at = NOW()
                        WHERE id = :id
                        """
                    ),
                    {"th": new_h, "id": lt_id},
                )
                updated += 1
    if deleted:
        print(f"  hash dedupe: deleted duplicate rows={deleted}, hash updated={updated}")

    return len(changed), len(work) - len(changed)


def _clean_unlinked_raw(engine) -> int:
    """dong raw 중 land_transactions 미생성분 clean.py 로 적재."""
    with engine.connect() as c:
        n = c.execute(
            text(
                """
                SELECT COUNT(*) FROM land_transactions_raw r
                WHERE r.raw_data->>'sigungu_name' ~ '^세종특별자치시\\s+[가-힣]+동\\s*$'
                  AND NOT EXISTS (SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id)
                """
            )
        ).scalar()
    if not n:
        return 0
    cmd = [sys.executable, str(_PIPELINE / "clean.py")]
    print(f"  unlinked dong raw {int(n)}건 → clean.py")
    subprocess.run(cmd, check=True, cwd=str(_PIPELINE))
    return int(n)


def _rebuild_stats(as_of: str, windows: str) -> None:
    for script, extra in (
        ("build_stats_v2.py", ["--sido-code", "36"]),
        ("build_upper_stats_v2.py", ["--sido-code", "36"]),
        (
            "build_annual_stats.py",
            ["--years", "2010-2026", "--sido-code", "36", "--with-upper"],
        ),
    ):
        cmd = [
            sys.executable,
            str(_PIPELINE / script),
            "--as-of",
            as_of,
            "--windows",
            windows,
            *extra,
        ]
        print(f"  $ {' '.join(cmd)}")
        subprocess.run(cmd, check=True, cwd=str(_PIPELINE))


def _summary(engine) -> None:
    with engine.connect() as c:
        n = c.execute(
            text(
                """
                SELECT COUNT(*) FROM land_transactions
                WHERE btrim(sido_code::text) = '36'
                  AND LEFT(btrim(beopjungri_code::text), 8) LIKE '361101%'
                """
            )
        ).scalar()
        print(f"\n[AFTER] sejong 361101xx txs: {int(n or 0)}")

        top = c.execute(
            text(
                """
                SELECT LEFT(btrim(beopjungri_code::text), 8) AS p8, COUNT(*)
                FROM land_transactions lt
                JOIN land_transactions_raw r ON r.id = lt.raw_id
                WHERE r.raw_data->>'sigungu_name' ~ '^세종특별자치시\\s+[가-힣]+동\\s*$'
                GROUP BY 1 ORDER BY 2 DESC LIMIT 10
                """
            )
        ).fetchall()
        print("[AFTER] dong raw → beop prefix:")
        for row in top:
            print(f"  {row.p8}: {int(row[1])}")


def main() -> int:
    p = argparse.ArgumentParser(description="세종 행정동(2토큰) beopjungri 재매핑")
    p.add_argument("--as-of", default="2026-05-01", help="stats v2 as_of_month")
    p.add_argument("--windows", default="3,5")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-clean-unlinked", action="store_true")
    p.add_argument("--skip-rebuild", action="store_true")
    args = p.parse_args()

    _load_env(_PIPELINE / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL 필요")

    engine = create_engine(url)
    region_maps = build_region_lookup(engine)

    df = _select_targets(engine)
    print(f"대상 거래: {len(df)}건 (세종 2토큰 동 주소)")

    if df.empty:
        print("처리할 행 없음")
        return 0

    mapped = map_beopjungri_codes(df, region_maps)
    new = mapped["beopjungri_code"].astype(str).str.strip()
    old = df["old_code"].astype(str).str.strip()
    ok = new.ne("") & ~mapped["needs_review"].astype(bool)
    print(f"  매핑 성공(예상): {int(ok.sum())}건 / 실패·review: {int((~ok).sum())}건")
    print(f"  코드 변경: {int((new != old).sum())}건")

    if args.dry_run:
        sample = pd.DataFrame(
            {
                "sigungu_name": df["sigungu_name"],
                "old": old,
                "new": new,
                "notes": mapped["mapping_notes"],
            }
        ).head(10)
        print(sample.to_string(index=False))
        return 0

    changed, kept = _apply_updates(engine, df, mapped)
    print(f"  UPDATE: changed={changed}, unchanged={kept}")

    if not args.skip_clean_unlinked:
        _clean_unlinked_raw(engine)

    if not args.skip_rebuild:
        print("\n== stats v2 / upper v2 재빌드 (sido 36) ==")
        _rebuild_stats(args.as_of, args.windows)

    _summary(engine)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
