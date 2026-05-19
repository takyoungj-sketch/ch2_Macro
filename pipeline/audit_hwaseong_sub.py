"""화성시 분구(만세구·동탄구·병점구 등) region_codes 적재 여부 확인."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from db_utils import get_engine

OUT = Path(__file__).resolve().parents[1] / "logs" / "audit_hwaseong.txt"
OUT.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    eng = get_engine()
    lines: list[str] = []
    with eng.connect() as conn:
        # 화성시 region_codes 시군구 단위
        r = conn.execute(
            text(
                """
                SELECT DISTINCT sigungu_code, sigungu_name
                FROM region_codes
                WHERE sigungu_name LIKE '%화성%' AND COALESCE(is_active, TRUE)
                ORDER BY sigungu_code
                """
            )
        ).fetchall()
        lines.append("[region_codes 화성 sigungu]")
        for row in r:
            lines.append(f"  {row[0]} {row[1]}")
        lines.append("")

        # 만세구 / 동탄구 / 병점구 존재 확인
        for q in ("만세구", "동탄구", "병점구", "남양구"):
            n = conn.execute(
                text("SELECT COUNT(*) FROM region_codes WHERE sigungu_name LIKE :p"),
                {"p": f"%{q}%"},
            ).scalar()
            lines.append(f"region_codes contains '{q}': {n}")
        lines.append("")

        # 실패 주소들의 (시도, 시군구, 읍면, 리) → region_codes 4튜플 lookup 실제 hit 여부
        sample = conn.execute(
            text(
                """
                SELECT DISTINCT
                  split_part(addr, ' ', 1) AS sido,
                  split_part(addr, ' ', 2) || ' ' || split_part(addr, ' ', 3) AS sgu,
                  split_part(addr, ' ', 4) AS umd,
                  split_part(addr, ' ', 5) AS leaf
                FROM (
                    SELECT COALESCE(r.raw_data->>'sigungu_name', '') AS addr
                    FROM land_transactions lt
                    JOIN land_transactions_raw r ON r.id = lt.raw_id
                    WHERE lt.needs_review = TRUE
                ) s
                WHERE array_length(string_to_array(addr, ' '), 1) = 5
                LIMIT 15
                """
            )
        ).fetchall()
        lines.append("[failing 5-token addresses parsed as (sido, sigungu5tok, umd, leaf)]")
        for row in sample:
            sido, sgu, umd, leaf = row
            hit = conn.execute(
                text(
                    """
                    SELECT beopjungri_code FROM region_codes
                    WHERE sido_name = :s AND sigungu_name = :g
                      AND eupmyeondong_name = :u AND beopjungri_name = :l
                      AND COALESCE(is_active, TRUE)
                    LIMIT 1
                    """
                ),
                {"s": sido, "g": sgu, "u": umd, "l": leaf},
            ).scalar()
            # 분구 제거 후 재시도: sigungu 첫 토큰만
            sgu2 = sgu.split()[0] if sgu else ""
            hit2 = conn.execute(
                text(
                    """
                    SELECT beopjungri_code FROM region_codes
                    WHERE sido_name = :s AND sigungu_name = :g
                      AND eupmyeondong_name = :u AND beopjungri_name = :l
                      AND COALESCE(is_active, TRUE)
                    LIMIT 1
                    """
                ),
                {"s": sido, "g": sgu2, "u": umd, "l": leaf},
            ).scalar()
            lines.append(
                f"  ({sido!r:8}, {sgu!r:25}, {umd!r:8}, {leaf!r:8}) "
                f"strict_hit={hit} sigungu_without_subgu={sgu2!r} hit={hit2}"
            )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}")


if __name__ == "__main__":
    main()
