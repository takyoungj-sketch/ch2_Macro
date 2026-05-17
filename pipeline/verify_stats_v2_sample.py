"""V2 소규모 검증 쿼리 — 실행: python verify_stats_v2_sample.py"""
from sqlalchemy import text

from db_utils import get_engine

AS_OF = "2024-04-01"
REGION = "4311311300"


def main() -> None:
    e = get_engine()
    with e.connect() as c:
        rows = c.execute(
            text(
                """
                SELECT window_years, period_start, period_end,
                       COUNT(*) AS nrows,
                       SUM(CASE WHEN zone_type = 'ALL' AND land_category = 'ALL' THEN 1 ELSE 0 END) AS n_totals
                FROM land_basic_stats_v2
                WHERE as_of_month = :as_of
                  AND btrim(beopjungri_code::text) = :region
                GROUP BY window_years, period_start, period_end
                ORDER BY window_years
                """
            ),
            {"as_of": AS_OF, "region": REGION},
        ).fetchall()
        print("=== land_basic_stats_v2 by window ===")
        for r in rows:
            print(dict(r._mapping))

        dup = c.execute(
            text(
                """
                SELECT COUNT(*) FROM (
                  SELECT as_of_month, window_years, beopjungri_code, zone_type, land_category, COUNT(*)
                  FROM land_basic_stats_v2
                  WHERE as_of_month = :as_of AND btrim(beopjungri_code::text) = :region
                  GROUP BY 1,2,3,4,5
                  HAVING COUNT(*) > 1
                ) t
                """
            ),
            {"as_of": AS_OF, "region": REGION},
        ).scalar()
        print("duplicate_grain_rows:", dup)

        # 원장 기준 ALL×ALL 건수 (contract_date, 동일 구간)
        for w in (3, 5):
            bounds = c.execute(
                text(
                    """
                    SELECT period_start, period_end
                    FROM land_basic_stats_v2
                    WHERE as_of_month = :as_of
                      AND btrim(beopjungri_code::text) = :region
                      AND window_years = :w
                      AND zone_type = 'ALL' AND land_category = 'ALL'
                    LIMIT 1
                    """
                ),
                {"as_of": AS_OF, "region": REGION, "w": w},
            ).fetchone()
            if not bounds:
                print("no bounds for window", w)
                continue
            ps, pe = bounds[0], bounds[1]
            cnt = c.execute(
                text(
                    """
                    SELECT COUNT(*) FROM land_transactions
                    WHERE is_valid AND NOT is_cancelled
                      AND unit_price_per_sqm IS NOT NULL
                      AND contract_date IS NOT NULL
                      AND contract_date >= :ps AND contract_date <= :pe
                      AND btrim(beopjungri_code::text) = :region
                    """
                ),
                {"ps": ps, "pe": pe, "region": REGION},
            ).scalar()
            stored = c.execute(
                text(
                    """
                    SELECT count FROM land_basic_stats_v2
                    WHERE as_of_month = :as_of AND window_years = :w
                      AND btrim(beopjungri_code::text) = :region
                      AND zone_type = 'ALL' AND land_category = 'ALL'
                    """
                ),
                {"as_of": AS_OF, "region": REGION, "w": w},
            ).scalar()
            print(f"window {w}: raw_count={cnt} stored_count={stored} period {ps}..{pe}")

        # v1 ALL×ALL 비교 (있을 때만)
        v1 = c.execute(
            text(
                """
                SELECT year_from, year_to, count, mean
                FROM land_basic_stats
                WHERE btrim(beopjungri_code::text) = :region
                  AND zone_type = 'ALL' AND land_category = 'ALL'
                ORDER BY year_from DESC
                LIMIT 3
                """
            ),
            {"region": REGION},
        ).fetchall()
        print("=== v1 latest ALL×ALL (up to 3 rows) ===")
        for r in v1:
            print(dict(r._mapping))


if __name__ == "__main__":
    main()
