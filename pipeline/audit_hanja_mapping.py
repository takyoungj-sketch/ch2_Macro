"""needs_review 거래 중 한자 병기(괄호) 패턴 비율 분석."""

from __future__ import annotations

import re

from sqlalchemy import text

from clean import _normalize_admin_label, _parse_address_structured
from db_utils import get_engine

_RE_PAREN_CJK = re.compile(r"[（(][^）)]*[\u4e00-\u9fff\u3400-\u4dbf]")
_RE_RI_PAREN = re.compile(r"[가-힣]+리[（(]")
_RE_DONG_PAREN = re.compile(r"[가-힣]+동[（(]")


def old_ri_branch_bug(addr: str) -> bool:
    """구 파서: 마지막 토큰이 정규화 후 리인데 raw는 )로 끝남."""
    parts = [p for p in str(addr).strip().split() if p]
    if not parts:
        return False
    last = parts[-1]
    last_norm = _normalize_admin_label(last)
    return bool(last_norm.endswith("리") and not last.endswith("리"))


def main() -> None:
    eng = get_engine()
    with eng.connect() as conn:
        review_rows = conn.execute(
            text(
                """
                SELECT lt.mapping_notes,
                       COALESCE(
                           r.raw_data->>'sigungu_name',
                           r.raw_data->>'시군구',
                           ''
                       ) AS addr,
                       lt.needs_review,
                       btrim(lt.beopjungri_code::text) AS bc
                FROM land_transactions lt
                JOIN land_transactions_raw r ON r.id = lt.raw_id
                WHERE lt.needs_review = TRUE
                """
            )
        ).fetchall()

        all_paren = conn.execute(
            text(
                """
                SELECT
                  COUNT(*)::int AS n,
                  COUNT(*) FILTER (WHERE lt.needs_review)::int AS n_review,
                  COUNT(*) FILTER (WHERE NOT lt.needs_review)::int AS n_ok
                FROM land_transactions lt
                JOIN land_transactions_raw r ON r.id = lt.raw_id
                WHERE COALESCE(r.raw_data->>'sigungu_name', '') ~ '[（(][^）)]*[\u4e00-\u9fff]'
                """
            )
        ).one()

        giam = conn.execute(
            text(
                """
                SELECT
                  COUNT(*)::int AS n,
                  COUNT(*) FILTER (WHERE lt.needs_review)::int AS n_review,
                  COUNT(*) FILTER (
                    WHERE btrim(lt.beopjungri_code::text) = '4311132026'
                  )::int AS n_mapped
                FROM land_transactions lt
                JOIN land_transactions_raw r ON r.id = lt.raw_id
                WHERE COALESCE(r.raw_data->>'sigungu_name', '') LIKE '%기암리%'
                """
            )
        ).one()

    rows = [(r[0], r[1]) for r in review_rows]
    total = len(rows)
    has_paren_cjk = 0
    ri_paren = 0
    dong_paren = 0
    ri_bug = 0
    other_paren = 0
    empty = 0

    for note, addr in rows:
        a = str(addr or "").strip()
        if not a:
            empty += 1
            continue
        if _RE_PAREN_CJK.search(a):
            has_paren_cjk += 1
        if _RE_RI_PAREN.search(a):
            ri_paren += 1
            if old_ri_branch_bug(a):
                ri_bug += 1
        elif _RE_DONG_PAREN.search(a):
            dong_paren += 1
        elif "(" in a or "（" in a:
            other_paren += 1

    def pct(n: int) -> str:
        return f"{100.0 * n / total:.1f}%" if total else "N/A"

    print(f"needs_review_total={total:,}")
    print(f"has_paren_cjk={has_paren_cjk:,} ({pct(has_paren_cjk)})")
    print(f"ri_paren_pattern={ri_paren:,} ({pct(ri_paren)})")
    print(f"  -> old_ri_branch_bug_subset={ri_bug:,} ({pct(ri_bug)} of all review)")
    print(f"dong_paren_pattern={dong_paren:,} ({pct(dong_paren)})")
    print(f"other_paren={other_paren:,} ({pct(other_paren)})")
    print(f"empty_addr={empty:,} ({pct(empty)})")
    print(f"no_paren_cjk={total - has_paren_cjk:,} ({pct(total - has_paren_cjk)})")
    print()
    print("--- all transactions with paren+CJK in sigungu_name ---")
    print(f"total={all_paren[0]:,} needs_review={all_paren[1]:,} mapped_ok={all_paren[2]:,}")
    if all_paren[0]:
        print(f"  review_rate={100.0*all_paren[1]/all_paren[0]:.1f}%")
    print("--- addresses containing 기암리 ---")
    print(f"total={giam[0]:,} needs_review={giam[1]:,} code_4311132026={giam[2]:,}")

    with eng.connect() as conn:
        any_cjk = conn.execute(
            text(
                """
                SELECT COUNT(*)::int AS n,
                       COUNT(*) FILTER (WHERE lt.needs_review)::int AS n_review
                FROM land_transactions lt
                JOIN land_transactions_raw r ON r.id = lt.raw_id
                WHERE COALESCE(r.raw_data->>'sigungu_name', '') ~ '[\u4e00-\u9fff]'
                """
            )
        ).one()
        giam_empty = conn.execute(
            text(
                """
                SELECT COUNT(*)::int FROM land_transactions lt
                JOIN land_transactions_raw r ON r.id = lt.raw_id
                WHERE COALESCE(r.raw_data->>'sigungu_name', '') LIKE '%기암리%'
                  AND btrim(COALESCE(lt.beopjungri_code::text, '')) = ''
                """
            )
        ).scalar()
        notes = conn.execute(
            text(
                """
                SELECT mapping_notes, COUNT(*)::int
                FROM land_transactions WHERE needs_review
                GROUP BY 1 ORDER BY 2 DESC
                """
            )
        ).fetchall()

    print("--- any CJK char in sigungu_name (not only parens) ---")
    print(f"total={any_cjk[0]:,} needs_review={any_cjk[1]:,}")
    if any_cjk[0]:
        print(f"  review_rate={100.0 * any_cjk[1] / any_cjk[0]:.1f}%")
    print(f"기암리 in addr but empty beopjungri_code={int(giam_empty or 0):,}")
    print("mapping_notes breakdown:", list(notes))

    with eng.connect() as conn:
        giam_codes = conn.execute(
            text(
                """
                SELECT btrim(lt.beopjungri_code::text) AS bc, COUNT(*)::int AS n
                FROM land_transactions lt
                JOIN land_transactions_raw r ON r.id = lt.raw_id
                WHERE COALESCE(r.raw_data->>'sigungu_name', '') LIKE '%기암리%'
                GROUP BY 1 ORDER BY n DESC LIMIT 10
                """
            )
        ).fetchall()
    print("기암리 addr beopjungri_code distribution:", list(giam_codes))


if __name__ == "__main__":
    main()
