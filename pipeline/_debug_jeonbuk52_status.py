"""Quick Jeonbuk 52 status: raw vs transactions vs annual."""
from sqlalchemy import text

from db_utils import get_engine


def main() -> None:
    e = get_engine()
    with e.connect() as c:
        unproc = c.execute(
            text(
                """
                SELECT COUNT(1) FROM land_transactions_raw r
                WHERE NOT EXISTS (
                  SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id
                )
                """
            )
        ).scalar()
        print("unprocessed raw total:", unproc)

        raw52 = c.execute(
            text(
                """
                SELECT LEFT(r.raw_data->>'deal_ymd', 4) AS yr, COUNT(1)
                FROM land_transactions_raw r
                WHERE r.raw_data->>'deal_ymd' LIKE '2010%'
                  AND (
                    r.raw_data->>'sigungu_code' LIKE '52%'
                    OR r.raw_data->>'sido_code' = '52'
                    OR r.source_file LIKE '%전북%'
                  )
                GROUP BY 1 ORDER BY 1
                """
            )
        ).fetchall()
        print("raw 2010 jeonbuk-ish by year prefix:", raw52)

        linked = c.execute(
            text(
                """
                SELECT COUNT(1) FROM land_transactions lt
                JOIN land_transactions_raw r ON r.id = lt.raw_id
                WHERE lt.contract_year IN (2010, 2011)
                  AND LEFT(btrim(lt.beopjungri_code::text), 2) = '52'
                """
            )
        ).scalar()
        print("transactions 2010-2011 with raw link (52):", linked)

        raw2010_unproc = c.execute(
            text(
                """
                SELECT COUNT(1) FROM land_transactions_raw r
                WHERE r.raw_data->>'deal_ymd' LIKE '2010%'
                  AND (
                    r.raw_data->>'sigungu_code' LIKE '52%'
                    OR r.raw_data->>'sido_code' = '52'
                    OR r.source_file LIKE '%전북%'
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id
                  )
                """
            )
        ).scalar()
        print("unprocessed raw 2010 jeonbuk:", raw2010_unproc)

        by_year_unproc = c.execute(
            text(
                """
                SELECT LEFT(r.raw_data->>'deal_ymd', 4) AS yr, COUNT(1)
                FROM land_transactions_raw r
                WHERE (
                    r.raw_data->>'sigungu_code' LIKE '52%'
                    OR r.raw_data->>'sido_code' = '52'
                    OR r.source_file LIKE '%전북%'
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id
                  )
                GROUP BY 1 ORDER BY 1
                """
            )
        ).fetchall()
        print("unprocessed jeonbuk raw by deal year:")
        for row in by_year_unproc:
            print(" ", row)


if __name__ == "__main__":
    main()
