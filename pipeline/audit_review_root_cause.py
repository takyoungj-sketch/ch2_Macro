"""needs_review 실패 원인을 패턴별로 분해."""

from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import text

from db_utils import get_engine

_CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_PAREN = re.compile(r"[（(][^）)]*[）)]?")


def main() -> None:
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                  COALESCE(r.raw_data->>'sigungu_name', '') AS addr,
                  COALESCE(r.raw_data->>'sigungu_code', '') AS sc,
                  COALESCE(r.raw_data->>'sido_code', '')    AS sido,
                  COALESCE(r.raw_data->>'eupmyeondong_name','') AS umd
                FROM land_transactions lt
                JOIN land_transactions_raw r ON r.id = lt.raw_id
                WHERE lt.needs_review = TRUE
                """
            )
        ).fetchall()

    total = len(rows)
    print(f"needs_review_total = {total:,}")

    tok_count: Counter[int] = Counter()
    has_paren = 0
    has_cjk = 0
    leaf_kind: Counter[str] = Counter()
    blanks_addr = 0
    no_sigungu_code = 0

    for addr, sc, sido, umd in rows:
        a = str(addr or "").strip()
        if not a:
            blanks_addr += 1
        if "(" in a or "（" in a:
            has_paren += 1
        if _CJK.search(a):
            has_cjk += 1
        if not str(sc or "").strip():
            no_sigungu_code += 1
        parts = a.split()
        tok_count[len(parts)] += 1
        if parts:
            last = parts[-1]
            if last.endswith("리"):
                leaf_kind["ri"] += 1
            elif last.endswith("동"):
                leaf_kind["dong"] += 1
            elif last.endswith("읍") or last.endswith("면"):
                leaf_kind["eupmyeon"] += 1
            elif _PAREN.search(last):
                leaf_kind["paren_tail"] += 1
            else:
                leaf_kind["other"] += 1

    def pct(n: int) -> str:
        return f"{100.0 * n / total:.1f}%" if total else "N/A"

    print(f"\n[address shape]")
    print(f"empty_addr        = {blanks_addr:,} ({pct(blanks_addr)})")
    print(f"has_paren_in_addr = {has_paren:,} ({pct(has_paren)})")
    print(f"has_CJK_in_addr   = {has_cjk:,} ({pct(has_cjk)})")
    print(f"missing_sigungu_code(JSON) = {no_sigungu_code:,} ({pct(no_sigungu_code)})")

    print(f"\n[address token count]")
    for k in sorted(tok_count):
        print(f"  {k} tokens: {tok_count[k]:,}")

    print(f"\n[leaf token kind]")
    for k, v in leaf_kind.most_common():
        print(f"  {k:12s}: {v:,} ({pct(v)})")

    # 시도 분포
    sido_dist: Counter[str] = Counter()
    for addr, sc, sido, umd in rows:
        a = str(addr or "").strip()
        if a:
            sido_dist[a.split()[0] if a else ""] += 1
    print(f"\n[top 시도 in failing addr]")
    for k, v in sido_dist.most_common(15):
        print(f"  {k:20s}: {v:,}")

    # 샘플 + 파일 저장
    from pathlib import Path

    out = Path(__file__).resolve().parents[1] / "logs" / "audit_review_samples.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    distinct: Counter[str] = Counter()
    for addr, sc, sido, umd in rows:
        distinct[str(addr or "").strip()] += 1
    lines = ["[top 30 distinct failing addresses with counts]"]
    for k, v in distinct.most_common(30):
        lines.append(f"  {v:6,}  {k}")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nsamples written to: {out}")
    print(f"distinct failing addresses: {len(distinct):,}")


if __name__ == "__main__":
    main()
