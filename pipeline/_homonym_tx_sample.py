"""UTF-8 homonym spot-check: land_transactions x region_codes (run from pipeline/)."""
from __future__ import annotations

from sqlalchemy import text

from db_utils import get_engine

NAMES = ("대장동", "신촌동", "중동", "본동", "장동", "덕은동")


def main() -> None:
    engine = get_engine()
    with engine.connect() as c:
        codes = [
            row[0]
            for row in c.execute(
                text(
                    """
                    SELECT beopjungri_code FROM region_codes
                    WHERE beopjungri_name = ANY(:names) AND is_active = TRUE
                    """
                ),
                {"names": list(NAMES)},
            )
        ]
        if not codes:
            print("No region_codes for names")
            return
        rows = c.execute(
            text(
                """
                SELECT
                  r.beopjungri_name,
                  r.sido_name,
                  r.sigungu_name,
                  r.eupmyeondong_name,
                  lt.beopjungri_code,
                  COUNT(*) AS tx_cnt,
                  COUNT(*) FILTER (WHERE lt.is_valid) AS valid_cnt
                FROM land_transactions lt
                JOIN region_codes r
                  ON r.beopjungri_code = btrim(lt.beopjungri_code::text)
                 AND r.is_active = TRUE
                WHERE lt.beopjungri_code = ANY(:codes)
                GROUP BY 1, 2, 3, 4, 5
                ORDER BY r.beopjungri_name, tx_cnt DESC
                """
            ),
            {"codes": codes},
        ).mappings().all()
    out_path = "homonym_tx_sample_utf8.txt"
    lines = []
    for row in rows:
        lines.append(
            "\t".join(
                str(row[k])
                for k in (
                    "beopjungri_name",
                    "sido_name",
                    "sigungu_name",
                    "eupmyeondong_name",
                    "beopjungri_code",
                    "tx_cnt",
                    "valid_cnt",
                )
            )
        )
    text_blob = "\n".join(lines) + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("name\tsido\tsigungu\teumdong\tcode\ttx\tvalid\n")
        f.write(text_blob)
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
