"""
동명이리(同名異里) 타겟 재매핑 — A 작업 (DECISIONS A안).

전국 reprocess(약 4시간) 없이, 영향받는 4개 코드 범위의 거래만
build_region_lookup → map_beopjungri_codes 로 다시 매핑한다.

영향 범위 (전수 점검 결과 — 동명이리 3건 중 양양 양리는 거래 0건):
- 4311132026 / 4311132033 : 충북 청주 상당구 미원면 기암리(岐岩/基岩)
- 4311425322 / 4311425350 : 충북 청주 흥덕구 오창읍 화산리(华山/花山)
- 4729025331 / 4729025332 : 강원 양양 현남면 양리(陽里/良里)   ← 거래 0건

스크립트 동작:
1) 영향 4개(+양리 2개) 코드와 같은 (sigungu_code, eupmyeondong_code) 안의 raw 거래 + 그 코드로 이미 매핑된 거래를 모은다.
2) 새 region_maps 로 재매핑 → land_transactions 의 beopjungri_code/needs_review/mapping_notes 업데이트.
3) land_basic_stats_v2 의 영향 코드 행 삭제 → build_stats_v2 의 --region 모드로 재빌드.

실행:
    py -3.13 pipeline/remap_homonym_targets.py --as-of 2025-12-01 --windows 3,5
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


_PIPELINE = Path(__file__).resolve().parent
if str(_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_PIPELINE))

from clean import build_region_lookup, map_beopjungri_codes  # noqa: E402


AFFECTED_CODES: tuple[str, ...] = (
    "4311132026",
    "4311132033",
    "4311425322",
    "4311425350",
    "4729025331",
    "4729025332",
)


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _select_target_raws(engine) -> pd.DataFrame:
    """영향 거래의 raw_id 와 매핑에 필요한 컬럼을 한 번에 로드.

    조건 (OR 합집합):
      1) 현재 4개(+양리 2) 코드로 매핑된 land_transactions
      2) raw sigungu_name 마지막에 '기암리(...)' / '화산리(...)' / '양리(...)' 가 들어 있는 거래
         (괄호 안 한자 분기 후보)
    """
    codes_sql = ",".join(f"'{c}'" for c in AFFECTED_CODES)
    sql = text(
        f"""
        SELECT lt.id AS lt_id,
               lt.raw_id,
               lt.beopjungri_code AS old_code,
               lt.needs_review    AS old_review,
               lt.mapping_notes   AS old_notes,
               r.raw_data->>'sigungu_name'    AS sigungu_name,
               r.raw_data->>'eupmyeondong_name' AS eupmyeondong_name,
               r.raw_data->>'sigungu_code'    AS sigungu_code,
               r.raw_data->>'sido_code'       AS sido_code
        FROM land_transactions lt
        JOIN land_transactions_raw r ON r.id = lt.raw_id
        WHERE btrim(lt.beopjungri_code::text) IN ({codes_sql})
           OR r.raw_data->>'sigungu_name' ~ '(기암리|화산리|양리)\\([^)]+\\)$'
        """
    )
    with engine.connect() as c:
        df = pd.read_sql(sql, c)
    return df


def _apply_remap(
    engine, df: pd.DataFrame, mapped: pd.DataFrame
) -> tuple[int, int]:
    """매핑 결과와 다른 행만 UPDATE. (changed_count, kept_count) 반환."""
    if df.empty:
        return 0, 0
    df = df.copy()
    df["new_code"] = mapped["beopjungri_code"].astype(str).str.strip()
    df["new_review"] = mapped["needs_review"].astype(bool)
    df["new_notes"] = mapped["mapping_notes"].astype(str)
    df["old_code"] = df["old_code"].astype(str).str.strip()
    df["old_notes"] = df["old_notes"].fillna("").astype(str)

    changed = df[
        (df["new_code"] != df["old_code"])
        | (df["new_review"] != df["old_review"].astype(bool))
        | (df["new_notes"] != df["old_notes"])
    ]
    if changed.empty:
        return 0, len(df)

    rows = [
        {
            "lt_id": int(r.lt_id),
            "bc": str(r.new_code) if str(r.new_code) else None,
            "rv": bool(r.new_review),
            "nt": str(r.new_notes) if str(r.new_notes) else None,
        }
        for r in changed.itertuples(index=False)
    ]
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE land_transactions
                SET beopjungri_code = :bc,
                    needs_review    = :rv,
                    mapping_notes   = :nt
                WHERE id = :lt_id
                """
            ),
            rows,
        )
    return len(changed), len(df) - len(changed)


def _delete_old_stats(engine) -> int:
    codes_sql = ",".join(f"'{c}'" for c in AFFECTED_CODES)
    with engine.begin() as conn:
        n = conn.execute(
            text(
                f"""
                DELETE FROM land_basic_stats_v2
                WHERE btrim(beopjungri_code::text) IN ({codes_sql})
                """
            )
        ).rowcount
    return int(n or 0)


def _rebuild_stats(as_of: str, windows: str) -> None:
    """build_stats_v2.py --region 으로 영향 4개 코드만 재빌드."""
    for code in AFFECTED_CODES:
        cmd = [
            sys.executable,
            str(_PIPELINE / "build_stats_v2.py"),
            "--as-of",
            as_of,
            "--windows",
            windows,
            "--region",
            code,
        ]
        print(f"  $ {' '.join(cmd)}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ! build_stats_v2 실패 (code={code})", file=sys.stderr)
            print(r.stdout, file=sys.stderr)
            print(r.stderr, file=sys.stderr)
            raise SystemExit(r.returncode)


def _summary(engine) -> None:
    codes_sql = ",".join(f"'{c}'" for c in AFFECTED_CODES)
    with engine.connect() as c:
        print("\n[AFTER] 영향 4개 코드 매핑 분포:")
        for r in c.execute(
            text(
                f"""
                SELECT btrim(beopjungri_code::text) AS bc, COUNT(*) AS n
                FROM land_transactions
                WHERE btrim(beopjungri_code::text) IN ({codes_sql})
                GROUP BY bc ORDER BY bc
                """
            )
        ):
            print(f"  {r.bc}: {int(r.n)}건")
        print("\n[AFTER] land_basic_stats_v2 영향 4개 코드 행 수:")
        for r in c.execute(
            text(
                f"""
                SELECT btrim(beopjungri_code::text) AS bc, COUNT(*) AS n
                FROM land_basic_stats_v2
                WHERE btrim(beopjungri_code::text) IN ({codes_sql})
                GROUP BY bc ORDER BY bc
                """
            )
        ):
            print(f"  {r.bc}: {int(r.n)}행")


def main() -> int:
    p = argparse.ArgumentParser(description="동명이리 disambiguation 타겟 재매핑")
    p.add_argument("--as-of", required=True, help="YYYY-MM-DD (예: 2025-12-01)")
    p.add_argument("--windows", default="3,5")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="UPDATE/DELETE/rebuild 없이 영향 건수만 확인",
    )
    args = p.parse_args()

    _load_env(_PIPELINE / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL 환경변수가 필요합니다.")
    engine = create_engine(url)

    print("== A 타겟 재매핑 시작 ==")
    print(f"  영향 코드: {', '.join(AFFECTED_CODES)}")
    region_maps = build_region_lookup(engine)
    if "disamb_by_name" not in region_maps:
        print("  ! region_maps 에 disamb_by_name 이 없습니다. clean.py 가 갱신됐는지 확인.")
        return 1
    print(f"  disambiguation 그룹: name={len(region_maps['disamb_by_name'])}")

    df = _select_target_raws(engine)
    print(f"  영향 raw 거래 행: {len(df)}건")

    if df.empty:
        print("  처리할 거래 없음 — 종료")
        return 0

    mapped = map_beopjungri_codes(df, region_maps)

    # 변경 미리보기
    new = mapped["beopjungri_code"].astype(str).str.strip()
    old = df["old_code"].astype(str).str.strip()
    delta = (new != old) | (mapped["needs_review"].astype(bool) != df["old_review"].astype(bool))
    print(f"  매핑 변경 예정: {int(delta.sum())}건")
    if int(delta.sum()) > 0:
        sample = pd.DataFrame(
            {
                "lt_id": df["lt_id"],
                "old": old,
                "new": new,
                "notes": mapped["mapping_notes"],
                "sigungu_name": df["sigungu_name"],
            }
        )[delta]
        # 분포 요약
        dist = sample.groupby(["old", "new", "notes"]).size().rename("n").reset_index()
        print("  변경 분포(old → new, notes):")
        for _, row in dist.iterrows():
            print(f"    {row['old']} → {row['new']}  notes='{row['notes']}'  ×{int(row['n'])}")

    if args.dry_run:
        print("  --dry-run: 적용 없이 종료")
        return 0

    changed, kept = _apply_remap(engine, df, mapped)
    print(f"  UPDATE 적용: changed={changed}, unchanged={kept}")

    deleted = _delete_old_stats(engine)
    print(f"  land_basic_stats_v2 영향 행 삭제: {deleted}")

    print("\n== build_stats_v2 (영향 4개 코드 재빌드) ==")
    _rebuild_stats(args.as_of, args.windows)

    _summary(engine)

    # land_upper_stats_v2 는 같은 시군구·읍면 안의 재분배라 합계 동일 → 재빌드 불필요.
    print(
        "\nNote: land_upper_stats_v2 는 동일 시군구·읍면 내 재분배라 합계 동일 → 재빌드 불요.\n"
        "Done."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
