# -*- coding: utf-8 -*-
"""Phase 1b — load code_reissue pairs into region_code_history (no tx/mart changes).

Reads Phase 1a CSV, inserts only change_type=code_reissue rows.
Unresolved / merge / split are skipped.

Usage:
  cd backend
  .venv/Scripts/python.exe ../pipeline/load_region_code_history_1b.py
  .venv/Scripts/python.exe ../pipeline/load_region_code_history_1b.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

CSV_1A = ROOT / "docs" / "reports" / "REGION_CODE_PHASE1A_CLASSIFICATION.csv"
OUT_MD = ROOT / "docs" / "reports" / "REGION_CODE_PHASE1B_VERIFY.md"
OUT_CSV = ROOT / "docs" / "reports" / "REGION_CODE_PHASE1B_VERIFY.csv"

# Gazette dates unknown per row; Phase 1b records mapping as-of master 260701.
# Year-level historical remap can refine effective_from later.
EFFECTIVE_FROM = date(2000, 1, 1)
SOURCE_BATCH = "phase1b_20260721_code_reissue_from_1a"


def _load_reissue_rows() -> list[dict]:
    rows = list(csv.DictReader(CSV_1A.open(encoding="utf-8-sig")))
    out = []
    for r in rows:
        if r.get("change_type") != "code_reissue":
            continue
        f = (r.get("historical_code") or "").strip()
        t = (r.get("canonical_code") or "").strip()
        if len(f) != 10 or len(t) != 10:
            continue
        out.append(r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from app.config import settings

    reissue = _load_reissue_rows()
    unresolved = [
        r
        for r in csv.DictReader(CSV_1A.open(encoding="utf-8-sig"))
        if r.get("change_type") == "unresolved"
    ]

    # Count clarification block for report
    count_note = (
        "집계: 존재누락 192 + 폐지활성 192 = 코드 384개. "
        "code_reissue 191쌍이 382개 코드 커버, unresolved 2행이 남은 2개 코드 "
        "(삼덕리 폐지활성 1 + 당포리 존재누락 1). "
        "분류 CSV 행수 193 = 191쌍 + 2단독 (대상 '192'는 한쪽 갭 크기)."
    )

    eng = create_engine(settings.database_url)
    before = after = inserted = skipped = 0
    verify_rows: list[dict] = []
    unres_check: list[dict] = []

    def _run(conn) -> None:
        nonlocal before, after, inserted, skipped, verify_rows, unres_check
        exists = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name='region_code_history'
                """
            )
        ).scalar()
        if not exists:
            raise RuntimeError(
                "region_code_history table missing — apply db/014_land_annual_stats.sql"
            )

        before = int(
            conn.execute(text("SELECT COUNT(*) FROM region_code_history")).scalar() or 0
        )

        for r in reissue:
            f = r["historical_code"].strip()
            t = r["canonical_code"].strip()
            note = (
                f"{SOURCE_BATCH} | {r.get('historical_name','')} → {r.get('canonical_name','')} "
                f"| {(r.get('rationale') or '')[:200]}"
            )
            tx_h = int(r.get("tx_count_historical") or 0)

            already = conn.execute(
                text(
                    """
                    SELECT id FROM region_code_history
                    WHERE from_code = :f AND to_code = :t AND change_type = 'code_reissue'
                    LIMIT 1
                    """
                ),
                {"f": f, "t": t},
            ).scalar()

            action = "skipped_existing"
            if already:
                skipped += 1
                action = "already_present"
            elif args.dry_run:
                inserted += 1
                action = "dry_run_would_insert"
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO region_code_history (
                            from_code, to_code, change_type,
                            effective_from, effective_to, source_note
                        ) VALUES (
                            :f, :t, 'code_reissue',
                            :ef, NULL, :note
                        )
                        """
                    ),
                    {"f": f, "t": t, "ef": EFFECTIVE_FROM, "note": note},
                )
                inserted += 1
                action = "inserted"

            if args.dry_run:
                present = True  # would be present after apply
            else:
                present = bool(
                    conn.execute(
                        text(
                            """
                            SELECT 1 FROM region_code_history
                            WHERE from_code = :f AND to_code = :t
                              AND change_type = 'code_reissue'
                            """
                        ),
                        {"f": f, "t": t},
                    ).scalar()
                )

            verify_rows.append(
                {
                    "historical_code": f,
                    "canonical_code": t,
                    "historical_name": r.get("historical_name") or "",
                    "canonical_name": r.get("canonical_name") or "",
                    "tx_count_historical": tx_h,
                    "mapping_ok": present,
                    "action": action,
                    "exemplar": r.get("exemplar") or "",
                }
            )

        after = int(
            conn.execute(text("SELECT COUNT(*) FROM region_code_history")).scalar() or 0
        )

        for vr in verify_rows:
            n = conn.execute(
                text(
                    "SELECT COUNT(*) FROM land_transactions WHERE beopjungri_code = :c"
                ),
                {"c": vr["historical_code"]},
            ).scalar()
            vr["tx_count_db"] = int(n or 0)

        for u in unresolved:
            f = (u.get("historical_code") or "").strip()
            mapped = False
            if f:
                mapped = bool(
                    conn.execute(
                        text(
                            "SELECT 1 FROM region_code_history WHERE from_code = :c LIMIT 1"
                        ),
                        {"c": f},
                    ).scalar()
                )
            unres_check.append(
                {
                    "historical_code": f,
                    "canonical_code": (u.get("canonical_code") or "").strip(),
                    "name": u.get("historical_name") or u.get("canonical_name") or "",
                    "has_from_mapping": mapped,
                }
            )

    if args.dry_run:
        with eng.connect() as conn:
            _run(conn)
    else:
        with eng.begin() as conn:
            _run(conn)

    # write reports
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    ok_n = sum(1 for v in verify_rows if v["mapping_ok"])
    fail_n = len(verify_rows) - ok_n
    sute = [v for v in verify_rows if v["historical_code"] == "4377034026"]

    lines = [
        "# Phase 1b — region_code_history 적재 검증",
        "",
        f"- **일자:** {date.today().isoformat()}",
        f"- **dry_run:** {args.dry_run}",
        f"- **소스:** `{CSV_1A.name}` 중 `code_reissue` only",
        f"- **batch:** `{SOURCE_BATCH}`",
        f"- **effective_from (일괄):** {EFFECTIVE_FROM.isoformat()} (고시일 미확정 — 추후 정제 가능)",
        "",
        "## 0. 숫자 확인 (192 vs 193)",
        "",
        count_note,
        "",
        "| 구분 | 수 |",
        "|------|---|",
        "| 존재 누락 (한쪽 갭) | 192 |",
        "| 폐지 활성 잔류 (한쪽 갭) | 192 |",
        "| code_reissue 쌍 | 191 |",
        "| unresolved 단독 행 | 2 |",
        "| 분류 CSV 총 행 | 193 (=191+2) |",
        "",
        "## 1. 적재 요약",
        "",
        f"| 항목 | 값 |",
        f"|------|----|",
        f"| history 행 수 (before) | {before} |",
        f"| history 행 수 (after) | {after if not args.dry_run else before + inserted - skipped} (dry-run 추정 가능) |",
        f"| 대상 code_reissue | {len(reissue)} |",
        f"| inserted / would_insert | {inserted} |",
        f"| already_present | {skipped} |",
        f"| 매핑 성공 (mapping_ok) | {ok_n} |",
        f"| 매핑 실패 | {fail_n} |",
        f"| unresolved 보류 | {len(unresolved)} (매핑 안 함) |",
        "",
        "## 2. 대소 수태리 exemplar",
        "",
    ]
    if sute:
        s = sute[0]
        lines += [
            f"- historical: `{s['historical_code']}` — {s['historical_name']}",
            f"- canonical: `{s['canonical_code']}` — {s['canonical_name']}",
            f"- tx (DB): {s.get('tx_count_db', s['tx_count_historical'])}",
            f"- mapping_ok: **{s['mapping_ok']}** ({s['action']})",
            "",
        ]
    else:
        lines += ["_수태리 행 없음_", ""]

    lines += [
        "## 3. unresolved 보류 (미매핑 확인)",
        "",
    ]
    for u in unres_check:
        lines.append(
            f"- hist=`{u['historical_code'] or '—'}` canon=`{u['canonical_code'] or '—'}` "
            f"{u['name']} — from_mapping={u['has_from_mapping']} (기대: False)"
        )
    lines += [
        "",
        "## 4. 매핑 목록 (tx 상위 40)",
        "",
        "| historical | canonical | historical name | canonical name | tx | mapping_ok |",
        "|------------|-----------|-----------------|----------------|----|------------|",
    ]
    for v in sorted(verify_rows, key=lambda x: -x.get("tx_count_db", x["tx_count_historical"]))[:40]:
        lines.append(
            f"| `{v['historical_code']}` | `{v['canonical_code']}` | "
            f"{v['historical_name']} | {v['canonical_name']} | "
            f"{v.get('tx_count_db', v['tx_count_historical'])} | {v['mapping_ok']} |"
        )
    if len(verify_rows) > 40:
        lines.append("")
        lines.append(f"_… 외 {len(verify_rows) - 40}건은 CSV 참고._")

    lines += [
        "",
        "## 5. 범위 밖 (이번 미실시)",
        "",
        "- `land_transactions` 원본/`beopjungri_code` 변경 없음",
        "- mart / `land_basic_stats_v2` 재빌드 없음",
        "- `region_codes` seed / is_active 변경 없음",
        "",
        "## 6. 다음 (Phase 2 후보)",
        "",
        "1. canonical resolve 로직 (history JOIN)",
        "2. 영향 mart/stats 재빌드",
        "3. GIS 선택 → canonical 통계 조회 테스트",
        "",
        f"상세 CSV: [`{OUT_CSV.name}`](./{OUT_CSV.name})",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    fields = [
        "historical_code",
        "canonical_code",
        "historical_name",
        "canonical_name",
        "tx_count_historical",
        "tx_count_db",
        "mapping_ok",
        "action",
        "exemplar",
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for v in sorted(verify_rows, key=lambda x: x["historical_code"]):
            w.writerow(v)

    print(
        f"dry_run={args.dry_run} reissue={len(reissue)} inserted={inserted} "
        f"skipped={skipped} mapping_ok={ok_n}/{len(verify_rows)} "
        f"before={before} after={after}"
    )
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_CSV}")
    print(count_note)
    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
