"""
충북 파일럿 End-to-End 검증 스크립트

파이프라인 실행 후 각 단계를 순서대로 확인한다.
DB에 접속이 필요하며, .env 환경변수(DATABASE_URL 또는 DB_*)가 설정돼 있어야 한다.

사용법:
    python verify_pilot.py                     # 전체 단계 확인
    python verify_pilot.py --step region       # region_codes 확인만
    python verify_pilot.py --step raw          # raw 적재 확인
    python verify_pilot.py --step clean        # 정제 결과 확인
    python verify_pilot.py --step stats        # 사전집계 확인
    python verify_pilot.py --step crosscheck   # 수치 교차검증 (샘플 동/리 지정 필요)
    python verify_pilot.py --step crosscheck --region 4311110100 --zone 계획관리 --cat 전

파이프라인 실행 순서 (이 스크립트 실행 전):
    1. python seed_region_codes.py --file 법정동코드_전체자료.txt --sido 충청북도
    2. python collect.py --mode excel --file C:/startcoding/GUKTO/토지_매매/충청북도_토지_매매_통합.xlsx
    3. python clean.py
    4. python build_stats.py
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import text

from db_utils import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SIDO_CODE_CHUNGBUK = "43"


def check_region_codes(engine) -> bool:
    """STEP 1: region_codes에 충북 데이터가 충분히 들어있는지 확인"""
    log.info("=" * 60)
    log.info("STEP 1: region_codes 확인 (충북, sido_code='%s')", SIDO_CODE_CHUNGBUK)
    log.info("=" * 60)

    with engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM region_codes WHERE sido_code = :sc"),
            {"sc": SIDO_CODE_CHUNGBUK},
        ).scalar()

        by_sigungu = conn.execute(
            text("""
                SELECT sigungu_name, COUNT(*) AS cnt
                FROM region_codes
                WHERE sido_code = :sc
                GROUP BY sigungu_name
                ORDER BY sigungu_name
            """),
            {"sc": SIDO_CODE_CHUNGBUK},
        ).fetchall()

    log.info("충북 법정동/리 총 %d개", total)
    for row in by_sigungu:
        log.info("  %-20s : %d개", row[0], row[1])

    ok = total > 0
    if not ok:
        log.error("[FAIL] region_codes가 비어있습니다. seed_region_codes.py 를 먼저 실행하세요.")
    else:
        log.info("[OK] region_codes 충북 데이터 확인 완료")
    return ok


def check_raw_table(engine) -> bool:
    """STEP 2: land_transactions_raw에 데이터가 적재됐는지 확인"""
    log.info("=" * 60)
    log.info("STEP 2: land_transactions_raw 적재 확인")
    log.info("=" * 60)

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM land_transactions_raw")).scalar()
        sample = conn.execute(
            text("SELECT id, source_year, source_month, loaded_at FROM land_transactions_raw LIMIT 3")
        ).fetchall()

    log.info("land_transactions_raw 총 %d행", total)
    for row in sample:
        log.info("  id=%s, year=%s, month=%s, loaded=%s", *row)

    ok = total > 0
    if not ok:
        log.error("[FAIL] raw 테이블이 비어있습니다. collect.py 를 실행하세요.")
    else:
        log.info("[OK] raw 적재 확인 완료")
    return ok


def check_clean_table(engine) -> bool:
    """STEP 3: land_transactions 정제 및 beopjungri_code 매핑 확인"""
    log.info("=" * 60)
    log.info("STEP 3: land_transactions 정제 결과 확인")
    log.info("=" * 60)

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM land_transactions")).scalar()
        valid = conn.execute(
            text("SELECT COUNT(*) FROM land_transactions WHERE is_valid = TRUE AND is_cancelled = FALSE")
        ).scalar()
        no_code = conn.execute(
            text("SELECT COUNT(*) FROM land_transactions WHERE beopjungri_code = '' OR beopjungri_code IS NULL")
        ).scalar()
        no_price = conn.execute(
            text("SELECT COUNT(*) FROM land_transactions WHERE unit_price_per_sqm IS NULL")
        ).scalar()

        sample = conn.execute(
            text("""
                SELECT beopjungri_code, sido_code, sigungu_code,
                       land_category, zone_type, unit_price_per_sqm
                FROM land_transactions
                WHERE is_valid = TRUE AND beopjungri_code != ''
                LIMIT 3
            """)
        ).fetchall()

    log.info("land_transactions 총 %d행 / 유효 %d행", total, valid)
    log.info("  beopjungri_code 미매핑: %d행", no_code)
    log.info("  unit_price_per_sqm 없음: %d행", no_price)
    for row in sample:
        log.info(
            "  beopjungri=%s, sido=%s, sigungu=%s, cat=%s, zone=%s, price=%.0f",
            *row,
        )

    ok = total > 0 and no_code < total * 0.5  # 50% 이상 매핑돼야 통과
    if not ok:
        log.error("[FAIL] beopjungri_code 미매핑 비율이 너무 높습니다. clean.py 재실행 또는 region_codes 확인.")
    else:
        if no_code > 0:
            log.warning("[WARN] beopjungri_code 미매핑 %d건 존재 (집계에서 제외됨)", no_code)
        log.info("[OK] 정제 결과 확인 완료")
    return ok


def check_basic_stats(engine) -> bool:
    """STEP 4: land_basic_stats 사전집계 생성 확인"""
    log.info("=" * 60)
    log.info("STEP 4: land_basic_stats 사전집계 확인")
    log.info("=" * 60)

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM land_basic_stats")).scalar()
        regions = conn.execute(
            text("SELECT COUNT(DISTINCT beopjungri_code) FROM land_basic_stats")
        ).scalar()
        sample = conn.execute(
            text("""
                SELECT b.beopjungri_code, r.sigungu_name, r.eupmyeondong_name, r.beopjungri_name,
                       b.zone_type, b.land_category, b.count, ROUND(b.mean) AS mean
                FROM land_basic_stats b
                LEFT JOIN region_codes r USING (beopjungri_code)
                WHERE b.zone_type != 'ALL' AND b.land_category != 'ALL' AND b.count >= 5
                ORDER BY b.count DESC
                LIMIT 5
            """)
        ).fetchall()

    log.info("land_basic_stats 총 %d행 / 법정동/리 %d개 포함", total, regions)
    for row in sample:
        log.info(
            "  %s %s %s | 용도=%s 지목=%s | n=%d 평균=%.0f원/㎡",
            row[1], row[2], row[3], row[4], row[5], row[6], row[7],
        )

    ok = total > 0
    if not ok:
        log.error("[FAIL] 사전집계가 비어있습니다. build_stats.py 를 실행하세요.")
    else:
        log.info("[OK] 사전집계 확인 완료")
    return ok


def check_crosscheck(engine, beopjungri_code: str, zone_type: str | None, land_category: str | None) -> None:
    """
    STEP 5: 특정 법정동/리의 통계 수치를 출력해 엑셀 결과물과 수작업으로 대조한다.

    출력 수치:
        n, 평균(원/㎡), 만원/㎡ 환산, CI하한, CI상한, 최소, P25, 중위, P75, 최대
    """
    log.info("=" * 60)
    log.info("STEP 5: 교차검증 — beopjungri_code=%s, zone=%s, cat=%s", beopjungri_code, zone_type, land_category)
    log.info("=" * 60)

    with engine.connect() as conn:
        # 지역명 조회
        region_name = conn.execute(
            text("SELECT sigungu_name, eupmyeondong_name, beopjungri_name FROM region_codes WHERE beopjungri_code = :c"),
            {"c": beopjungri_code},
        ).fetchone()

        params: dict = {"code": beopjungri_code}
        zone_filter = ""
        cat_filter = ""
        if zone_type:
            zone_filter = "AND zone_type = :zone"
            params["zone"] = zone_type
        if land_category:
            cat_filter = "AND land_category = :cat"
            params["cat"] = land_category

        rows = conn.execute(
            text(f"""
                SELECT zone_type, land_category,
                       count, mean, ci_lower, ci_upper,
                       p_min, p25, median, p75, p_max
                FROM land_basic_stats
                WHERE beopjungri_code = :code
                  {zone_filter}
                  {cat_filter}
                  AND zone_type != 'ALL' AND land_category != 'ALL'
                ORDER BY zone_type, land_category
            """),
            params,
        ).fetchall()

    if region_name:
        log.info("지역: %s %s %s", *region_name)
    else:
        log.warning("region_codes 에서 지역명을 찾을 수 없음 (코드: %s)", beopjungri_code)

    if not rows:
        log.error("해당 조건의 집계 결과가 없습니다.")
        return

    log.info("\n%-10s %-6s | %5s %12s %12s %12s %12s %12s %12s %12s %12s",
             "용도지역", "지목", "n", "평균(원/㎡)", "만원/㎡", "CI하한", "CI상한",
             "최소", "P25", "중위", "P75")
    log.info("-" * 130)
    for r in rows:
        zone, cat, n, mean, ci_l, ci_u, p_min, p25, med, p75, p_max = r
        mean_10k = (mean or 0) / 10000
        log.info(
            "%-10s %-6s | %5d %12.0f %12.2f %12.0f %12.0f %12.0f %12.0f %12.0f %12.0f",
            zone, cat, n, mean or 0, mean_10k, ci_l or 0, ci_u or 0,
            p_min or 0, p25 or 0, med or 0, p75 or 0,
        )
    log.info("\n엑셀 결과물의 단가 단위가 만원/㎡ 이라면 '만원/㎡' 열과 비교하세요.")


def main() -> None:
    parser = argparse.ArgumentParser(description="충북 파일럿 End-to-End 검증")
    parser.add_argument(
        "--step",
        choices=["region", "raw", "clean", "stats", "crosscheck", "all"],
        default="all",
        help="실행할 검증 단계 (default: all)",
    )
    parser.add_argument("--region", type=str, default=None, help="교차검증용 beopjungri_code (10자리)")
    parser.add_argument("--zone", type=str, default=None, help="교차검증용 용도지역 (예: 계획관리)")
    parser.add_argument("--cat", type=str, default=None, help="교차검증용 지목 (예: 전)")
    args = parser.parse_args()

    engine = get_engine()
    results = {}

    if args.step in ("region", "all"):
        results["region"] = check_region_codes(engine)
    if args.step in ("raw", "all"):
        results["raw"] = check_raw_table(engine)
    if args.step in ("clean", "all"):
        results["clean"] = check_clean_table(engine)
    if args.step in ("stats", "all"):
        results["stats"] = check_basic_stats(engine)

    if args.step == "crosscheck":
        if not args.region:
            log.error("--region (beopjungri_code 10자리) 를 지정하세요.")
            sys.exit(1)
        check_crosscheck(engine, args.region, args.zone, args.cat)
        return

    fails = [k for k, v in results.items() if not v]
    if fails:
        log.error("\n[SUMMARY] 실패 단계: %s", ", ".join(fails))
        sys.exit(1)
    else:
        log.info("\n[SUMMARY] 모든 검증 통과")


if __name__ == "__main__":
    main()
