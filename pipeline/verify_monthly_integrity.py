#!/usr/bin/env python3
"""
월간 Promote 전 통합 정합성 검증 (L1 불변식 + L2 골든 앵커).

읽기 전용 — DB 를 변경하지 않는다 (--update-golden 은 fixture JSON 만 갱신).

사용:
    cd pipeline
    python verify_monthly_integrity.py --as-of-month 2026-05-01
    python verify_monthly_integrity.py --as-of-month 2026-05-01 --base-url http://127.0.0.1:8000
    python verify_monthly_integrity.py --as-of-month 2026-05-01 --update-golden
    python verify_monthly_integrity.py --as-of-month 2026-05-01 \\
        --count-before ../clean_snapshots/202605/land_tx_counts_after.json \\
        --count-after ../clean_snapshots/202606/land_tx_counts_after.json

exit 0 = Promote 게이트 통과, 1 = 실패.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import text

from build_stats_v2 import parse_as_of_month, period_bounds_for_window
from db_utils import get_engine

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
FIXTURE_DEFAULT = ROOT / "fixtures" / "golden_monthly_integrity.json"
ARTIFACT_DEFAULT = REPO / "logs" / "verify_monthly_integrity.txt"

DEDUPE_EXTRA_ROWS_SQL = """
SELECT COALESCE(SUM(cnt - 1), 0)::bigint
FROM (
  SELECT COUNT(*) AS cnt
  FROM land_transactions
  WHERE is_valid = TRUE
  GROUP BY beopjungri_code, contract_date, area_sqm, total_price_10k,
           COALESCE(land_category, ''), COALESCE(zone_type, ''), is_cancelled
  HAVING COUNT(*) > 1
) s
"""

V2_DUP_GRAIN_SQL = """
SELECT COUNT(*) FROM (
  SELECT as_of_month, window_years, beopjungri_code, zone_type, land_category, COUNT(*)
  FROM land_basic_stats_v2
  WHERE as_of_month = :as_of
  GROUP BY 1, 2, 3, 4, 5
  HAVING COUNT(*) > 1
) t
"""

RAW_COUNT_SQL = """
SELECT COUNT(*) FROM land_transactions
WHERE is_valid AND NOT is_cancelled
  AND unit_price_per_sqm IS NOT NULL
  AND contract_date IS NOT NULL
  AND contract_date >= :ps AND contract_date <= :pe
  AND btrim(beopjungri_code::text) = :region
"""

STORED_COUNT_SQL = """
SELECT count FROM land_basic_stats_v2
WHERE as_of_month = :as_of AND window_years = :w
  AND btrim(beopjungri_code::text) = :region
  AND zone_type = 'ALL' AND land_category = 'ALL'
"""

PERIOD_BOUNDS_SQL = """
SELECT DISTINCT window_years, period_start, period_end
FROM land_basic_stats_v2
WHERE as_of_month = :as_of
ORDER BY window_years
"""


for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    try:
        if _stream is not None and hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.errors = 0
        self.warnings = 0

    def section(self, title: str) -> None:
        line = f"\n=== {title} ==="
        print(line)
        self.lines.append(line)

    def ok(self, msg: str) -> None:
        line = f"  [OK] {msg}"
        print(line)
        self.lines.append(line)

    def warn(self, msg: str) -> None:
        self.warnings += 1
        line = f"  [WARN] {msg}"
        print(line)
        self.lines.append(line)

    def err(self, msg: str) -> None:
        self.errors += 1
        line = f"  [ERR] {msg}"
        print(line)
        self.lines.append(line)

    def info(self, msg: str) -> None:
        line = f"        {msg}"
        print(line)
        self.lines.append(line)


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_fixture(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_as_of_present(conn, rep: Report, as_of: date) -> bool:
    n = conn.execute(
        text("SELECT COUNT(*) FROM land_basic_stats_v2 WHERE as_of_month = :a"),
        {"a": as_of},
    ).scalar()
    cnt = int(n or 0)
    if cnt <= 0:
        rep.err(f"land_basic_stats_v2 에 as_of_month={as_of} 행 없음 — V2 배치 먼저 실행")
        return False
    rep.ok(f"land_basic_stats_v2 as_of={as_of} rows={cnt:,}")
    return True


def check_ledger_duplicates(conn, rep: Report) -> None:
    extra = int(conn.execute(text(DEDUPE_EXTRA_ROWS_SQL)).scalar() or 0)
    if extra == 0:
        rep.ok("land_transactions business-key 중복 extra_rows=0")
    else:
        rep.err(f"land_transactions 중복 extra_rows={extra:,} — dedupe 필요")


def check_v2_grain(conn, rep: Report, as_of: date) -> None:
    dup = int(
        conn.execute(text(V2_DUP_GRAIN_SQL), {"as_of": as_of}).scalar() or 0
    )
    if dup == 0:
        rep.ok(f"V2 grain 중복 0 (as_of={as_of})")
    else:
        rep.err(f"V2 grain 중복 {dup}건 — UNIQUE 위반")


def check_period_bounds(conn, rep: Report, as_of: date) -> None:
    rows = conn.execute(text(PERIOD_BOUNDS_SQL), {"as_of": as_of}).fetchall()
    if not rows:
        rep.err("V2 period bounds 행 없음")
        return
    bad = 0
    for r in rows:
        w = int(r.window_years)
        ps, pe = r.period_start, r.period_end
        exp_ps, exp_pe = period_bounds_for_window(as_of, w)
        if ps != exp_ps or pe != exp_pe:
            rep.err(
                f"window={w} period 불일치: stored {ps}..{pe} "
                f"expected {exp_ps}..{exp_pe}"
            )
            bad += 1
    if bad == 0:
        rep.ok(f"period_bounds_for_window 일치 ({len(rows)} window 그룹)")


def raw_and_stored_count(
    conn, as_of: date, region: str, window_years: int
) -> tuple[int | None, int | None, date | None, date | None]:
    bounds = conn.execute(
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
        {"as_of": as_of, "region": region, "w": window_years},
    ).fetchone()
    if not bounds:
        return None, None, None, None
    ps, pe = bounds[0], bounds[1]
    raw = int(
        conn.execute(
            text(RAW_COUNT_SQL), {"ps": ps, "pe": pe, "region": region}
        ).scalar()
        or 0
    )
    stored = conn.execute(
        text(STORED_COUNT_SQL),
        {"as_of": as_of, "region": region, "w": window_years},
    ).scalar()
    stored_i = int(stored) if stored is not None else None
    return raw, stored_i, ps, pe


def check_v2_raw_match(
    conn,
    rep: Report,
    as_of: date,
    region: str,
    label: str,
    windows: list[int],
    *,
    count_floors: dict[str, dict[str, int]] | None = None,
    expected_counts: dict[str, dict[str, int]] | None = None,
) -> dict[str, int]:
    """원장 count == V2 ALL×ALL. 반환: {window_str: stored_count} (--update-golden 용)."""
    floors = (count_floors or {}).get(region, {})
    expected = (expected_counts or {}).get(region, {})
    observed: dict[str, int] = {}
    for w in windows:
        raw, stored, ps, pe = raw_and_stored_count(conn, as_of, region, w)
        if stored is None:
            exp_ps, exp_pe = period_bounds_for_window(as_of, w)
            if ps is None:
                ps, pe = exp_ps, exp_pe
                raw = int(
                    conn.execute(
                        text(RAW_COUNT_SQL), {"ps": ps, "pe": pe, "region": region}
                    ).scalar()
                    or 0
                )
            if raw == 0:
                rep.ok(
                    f"{label} ({region}) w={w}: 거래 0건 — V2 ALL×ALL 생략 (정상)"
                )
                observed[str(w)] = 0
                continue
            rep.err(f"{label} ({region}) w={w}: raw={raw} but V2 ALL×ALL 행 없음")
            continue
        observed[str(w)] = stored
        floor = floors.get(str(w))
        if floor is not None and stored < floor:
            rep.err(f"{label} w={w} count={stored} < floor={floor}")
        exp = expected.get(str(w))
        if exp is not None and stored != exp:
            rep.err(
                f"{label} w={w} count={stored} != golden expected={exp} "
                f"(의도적 변경이면 --update-golden)"
            )
        if raw != stored:
            rep.err(
                f"{label} ({region}) w={w}: raw={raw} != stored={stored} "
                f"period {ps}..{pe}"
            )
        else:
            rep.ok(f"{label} ({region}) w={w}: raw=stored={stored}")
    return observed


def check_ledger_exact(conn, rep: Report, item: dict[str, Any]) -> None:
    label = item.get("label") or item.get("id")
    code = item["beopjungri_code"]
    exp = int(item["expected_count"])
    cnt = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM land_transactions
                WHERE btrim(beopjungri_code::text) = :code
                  AND zone_type = :zone AND land_category = :cat
                  AND is_valid = TRUE
                """
            ),
            {
                "code": code,
                "zone": item["zone_type"],
                "cat": item["land_category"],
            },
        ).scalar()
        or 0
    )
    if cnt == exp:
        rep.ok(f"{label}: ledger count={cnt}")
    else:
        rep.err(f"{label}: ledger count={cnt}, expected={exp}")


def check_api_vs_db(
    conn,
    rep: Report,
    base_url: str,
    as_of: date,
    samples: list[dict[str, Any]],
    windows: list[int],
) -> None:
    rep.section("L1 API ↔ DB count (optional)")
    session = requests.Session()
    as_s = as_of.isoformat()
    for sample in samples:
        code = sample["beopjungri_code"]
        label = sample.get("label") or code
        for w in windows:
            url = f"{base_url.rstrip('/')}/api/free/v2/stats/{code}"
            try:
                r = session.get(
                    url,
                    params={"window_years": w, "as_of_month": as_s},
                    timeout=120,
                )
            except requests.RequestException as exc:
                rep.err(f"{label} w={w} API network: {exc}")
                continue
            if r.status_code == 404:
                rep.warn(f"{label} w={w} API 404 — 사전집계 없음 또는 코드 오류")
                continue
            if r.status_code != 200:
                rep.err(f"{label} w={w} API HTTP {r.status_code}")
                continue
            api_count = int((r.json().get("total") or {}).get("count") or -1)
            _, stored, _, _ = raw_and_stored_count(conn, as_of, code, w)
            if stored is None:
                rep.warn(f"{label} w={w} API n={api_count}, DB V2 없음")
            elif api_count != stored:
                rep.err(
                    f"{label} w={w} API count={api_count} != DB stored={stored}"
                )
            else:
                rep.ok(f"{label} w={w} API=DB={api_count}")


def compare_count_snapshots(
    rep: Report, before: Path, after: Path, ratio_warn: float
) -> None:
    rep.section("L3 시도별 건수 스냅샷 diff (optional)")
    if not before.is_file():
        rep.warn(f"before 스냅샷 없음: {before}")
        return
    if not after.is_file():
        rep.warn(f"after 스냅샷 없음: {after}")
        return
    b = json.loads(before.read_text(encoding="utf-8"))
    a = json.loads(after.read_text(encoding="utf-8"))
    bs = b.get("by_sido") or {}
    aa = a.get("by_sido") or {}
    rep.info(f"before total={b.get('total')} after total={a.get('total')}")
    issues = 0
    for k in sorted(set(bs) | set(aa)):
        nb = int(bs.get(k, 0))
        na = int(aa.get(k, 0))
        if na == 0 and nb > 0:
            rep.err(f"[누락?] sido={k!r}: before={nb} → after=0")
            issues += 1
        elif nb > 0 and na > 0:
            ch = abs(na - nb) / nb
            if ch >= ratio_warn:
                rep.err(
                    f"[급변] sido={k!r}: before={nb} after={na} "
                    f"(|Δ|/before={ch:.2%})"
                )
                issues += 1
    if issues == 0:
        rep.ok("시도별 건수 스냅샷 특이사항 없음")


def resolve_as_of_month(arg: str | None) -> date:
    if arg:
        return parse_as_of_month(arg)
    raw = os.environ.get("STATS_V2_DEFAULT_AS_OF_MONTH", "").strip()
    if raw:
        return parse_as_of_month(raw)
    with get_engine().connect() as conn:
        latest = conn.execute(
            text("SELECT MAX(as_of_month) FROM land_basic_stats_v2")
        ).scalar()
    if latest is None:
        raise SystemExit("as_of_month 미지정 — DB 에 V2 없음")
    if isinstance(latest, date):
        return latest
    return parse_as_of_month(str(latest))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="월간 Promote 전 통합 정합성 검증 (L1+L2)"
    )
    parser.add_argument(
        "--as-of-month",
        default=None,
        help="V2 as_of_month (YYYY-MM-01). 생략 시 env 또는 DB MAX",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=FIXTURE_DEFAULT,
        help="골든 fixture JSON",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("VERIFY_V2_API_BASE", "").strip() or None,
        help="지정 시 API total.count ↔ DB 대조",
    )
    parser.add_argument(
        "--windows",
        default="3,5",
        help="검증 window_years (쉼표)",
    )
    parser.add_argument(
        "--count-before",
        type=Path,
        default=None,
        help="이전 land_tx_counts_after.json",
    )
    parser.add_argument(
        "--count-after",
        type=Path,
        default=None,
        help="이번 land_tx_counts_after.json",
    )
    parser.add_argument(
        "--ratio-warn",
        type=float,
        default=0.35,
        help="스냅샷 diff 급변 임계 (기본 35%%)",
    )
    parser.add_argument(
        "--update-golden",
        action="store_true",
        help="fixture expected_v2_counts 만 현재 DB 값으로 갱신 후 종료",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=ARTIFACT_DEFAULT,
        help="결과 로그 저장 경로",
    )
    parser.add_argument(
        "--skip-national-raw-match",
        action="store_true",
        help="전국 샘플 raw↔stored 검사 생략 (속도)",
    )
    args = parser.parse_args()

    try:
        windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    except ValueError:
        raise SystemExit("invalid --windows") from None

    as_of = resolve_as_of_month(args.as_of_month)
    fixture = load_fixture(args.fixture)
    as_of_key = as_of.isoformat()

    rep = Report()
    rep.section(f"verify_monthly_integrity as_of={as_of_key}")

    engine = get_engine()
    golden_updates: dict[str, dict[str, int]] = {}

    with engine.connect() as conn:
        if not check_as_of_present(conn, rep, as_of):
            pass
        else:
            rep.section("L1 원장·V2 불변식")
            check_ledger_duplicates(conn, rep)
            check_v2_grain(conn, rep, as_of)
            check_period_bounds(conn, rep, as_of)

            rep.section("L2 골든 앵커 — ledger_exact")
            for item in fixture.get("ledger_exact") or []:
                check_ledger_exact(conn, rep, item)

            rep.section("L2 골든 앵커 — v2_raw_match")
            count_floors = fixture.get("count_floors") or {}
            expected_all = (fixture.get("expected_v2_counts") or {}).get(
                as_of_key, {}
            )
            for item in fixture.get("v2_raw_match") or []:
                obs = check_v2_raw_match(
                    conn,
                    rep,
                    as_of,
                    item["beopjungri_code"],
                    item.get("label") or item.get("id", ""),
                    item.get("windows") or windows,
                    count_floors=count_floors,
                    expected_counts={item["beopjungri_code"]: expected_all}
                    if expected_all
                    else None,
                )
                if obs:
                    golden_updates[item["beopjungri_code"]] = obs

            if not args.skip_national_raw_match:
                rep.section("L1 전국 샘플 raw↔stored")
                seen: set[str] = set()
                for sample in fixture.get("national_samples") or []:
                    code = sample["beopjungri_code"]
                    if code in seen:
                        continue
                    seen.add(code)
                    check_v2_raw_match(
                        conn,
                        rep,
                        as_of,
                        code,
                        sample.get("label") or code,
                        windows,
                        count_floors=None,
                        expected_counts=None,
                    )

            if args.base_url:
                check_api_vs_db(
                    conn,
                    rep,
                    args.base_url,
                    as_of,
                    fixture.get("national_samples") or [],
                    windows,
                )

    if args.count_before and args.count_after:
        compare_count_snapshots(
            rep, args.count_before, args.count_after, args.ratio_warn
        )

    rep.section("요약")
    summary = (
        f"errors={rep.errors} warnings={rep.warnings} "
        f"as_of={as_of_key} promote_gate={'PASS' if rep.errors == 0 else 'FAIL'}"
    )
    print(summary)
    rep.lines.append(summary)

    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text("\n".join(rep.lines) + "\n", encoding="utf-8")
    rep.info(f"artifact: {args.artifact}")

    if args.update_golden:
        if not golden_updates:
            raise SystemExit("--update-golden: v2_raw_match 관측값 없음")
        ev = fixture.setdefault("expected_v2_counts", {})
        ev[as_of_key] = golden_updates
        save_fixture(args.fixture, fixture)
        print(f"[OK] fixture 갱신: {args.fixture} → expected_v2_counts[{as_of_key}]")
        raise SystemExit(0 if rep.errors == 0 else 1)

    raise SystemExit(0 if rep.errors == 0 else 1)


if __name__ == "__main__":
    main()
