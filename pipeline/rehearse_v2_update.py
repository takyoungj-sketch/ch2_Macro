"""
2026년 첫 V2 갱신 리허설 — 읽기 전용 점검 도구.

목적
====
`docs/V2_OPERATOR_CHECKLIST.md` §B(월별 표준 갱신) 12 단계가 실제로 돌릴 수 있는
상태인지를, **DB 를 변경하지 않고** 미리 점검한다.

체크 항목
---------
1. 환경
   - backend/.env, pipeline/.env, frontend/.env 존재 여부 (필수는 backend/pipeline)
   - DATABASE_URL 또는 DB_* 환경변수로 엔진 생성 가능?
2. 마이그레이션 스냅샷 (information_schema)
   - land_transactions, land_basic_stats_v2, land_basic_stats(V1), region_codes,
     population_jusosagae, analysis_cache, analysis_base_cache 존재 여부
3. 데이터 스냅샷
   - 각 테이블 행수
   - land_basic_stats_v2.as_of_month 분포 (DISTINCT, MAX)
   - V2 최신 as_of_month 가 어느 달의 「YYYY년 M월 말 기준」인지
4. SOP §B 명령들의 dry-run
   - run_pipeline.py / build_stats_v2.py / seed_population_csv.py
     verify_v2_national_samples.py 의 `--help` 가 깨지지 않고 호출되는지
5. (옵션) 백엔드가 떠 있다면 GET /health 의 latest_as_of_month 까지 같이 본다.

이 스크립트는 **TRUNCATE/INSERT/UPDATE 등을 절대 하지 않는다**. 안전하다.

사용
----
    python rehearse_v2_update.py
    python rehearse_v2_update.py --health-url http://127.0.0.1:8000/health
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import text

from db_utils import get_engine

# Windows cp949 콘솔에서도 한글·em-dash 출력이 깨지지 않게 stdout/stderr 를 UTF-8 로
# 재설정한다(파이썬 3.7+ 의 reconfigure). 안 되면 errors='replace' 로 폴백.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    try:
        if _stream is not None and hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
PY = sys.executable

# 리허설 산출물 — 단순 텍스트로 모아 운영 로그에 남기기 좋게.
ARTIFACT_DEFAULT = REPO / "logs" / "rehearse_v2_update.txt"


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------


class Report:
    """리허설 결과 누적기. 콘솔에도 같이 찍는다."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.errors: int = 0
        self.warnings: int = 0

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


def as_of_label(d: date | None) -> str:
    """as_of_month(YYYY-MM-01) → 「YYYY년 M월 말 기준」(라벨 통일 검증용)."""
    if d is None:
        return "—"
    return f"{d.year}년 {d.month}월 말 기준"


def table_count(engine: Any, qualified: str) -> int | None:
    try:
        with engine.connect() as conn:
            return int(
                conn.execute(text(f"SELECT COUNT(*) FROM {qualified}")).scalar() or 0
            )
    except Exception:
        return None


def table_exists(engine: Any, name: str) -> bool:
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema=current_schema() AND table_name=:n LIMIT 1"
                ),
                {"n": name},
            ).first()
        return row is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 1) 환경 점검
# ---------------------------------------------------------------------------


def check_env(rep: Report) -> None:
    rep.section("1) 환경 (.env, DB 접속)")

    for rel in ("backend/.env", "pipeline/.env"):
        p = REPO / rel
        if p.exists():
            rep.ok(f"{rel} 존재")
        else:
            rep.warn(f"{rel} 없음 — 갱신 시 필수")

    # frontend 는 빌드 타임에 쓰이므로 정보용
    fe = REPO / "frontend" / ".env"
    rep.info(f"frontend/.env: {'있음' if fe.exists() else '없음(개발 시 선택)'}")

    try:
        engine = get_engine()
        with engine.connect() as conn:
            ver = conn.execute(text("SELECT version()")).scalar()
        rep.ok("DB 접속 성공")
        rep.info(str(ver).split(",")[0])
    except Exception as exc:  # pragma: no cover
        rep.err(f"DB 접속 실패: {exc!r}")


# ---------------------------------------------------------------------------
# 2) 마이그레이션 + 3) 데이터 스냅샷
# ---------------------------------------------------------------------------


REQUIRED_TABLES = [
    "land_transactions",
    "land_basic_stats_v2",
    "land_basic_stats",
    "region_codes",
    "population_jusosagae",
    "analysis_cache",
    "analysis_base_cache",
]


def check_db_snapshot(rep: Report) -> dict[str, Any]:
    rep.section("2) 테이블 존재 여부")
    snapshot: dict[str, Any] = {}
    try:
        engine = get_engine()
    except Exception as exc:
        rep.err(f"엔진 생성 실패 — 이후 단계 생략: {exc!r}")
        return snapshot

    for t in REQUIRED_TABLES:
        if table_exists(engine, t):
            rep.ok(f"{t} 존재")
        else:
            rep.err(f"{t} 없음 — db/00*.sql 적용 필요")

    rep.section("3) 행수·신선도 스냅샷")
    for t in REQUIRED_TABLES:
        cnt = table_count(engine, t)
        snapshot[f"count_{t}"] = cnt
        if cnt is None:
            rep.warn(f"{t}: 조회 실패")
        else:
            rep.ok(f"{t} 행수 = {cnt:,}")

    # land_basic_stats_v2 분포
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT as_of_month::date AS m, window_years, COUNT(*) AS n
                      FROM land_basic_stats_v2
                     GROUP BY as_of_month, window_years
                     ORDER BY as_of_month DESC, window_years
                     LIMIT 20
                    """
                )
            ).all()
        if not rows:
            rep.warn("land_basic_stats_v2 비어있음 — 첫 갱신 전 상태일 수 있음")
        else:
            rep.ok("land_basic_stats_v2 (as_of_month, window_years, n) — 최근 20")
            for r in rows:
                rep.info(f"{r.m}  win={r.window_years}  rows={int(r.n):,}")
        with engine.connect() as conn:
            latest = conn.execute(
                text("SELECT MAX(as_of_month)::date FROM land_basic_stats_v2")
            ).scalar()
        snapshot["latest_as_of_month"] = latest.isoformat() if latest else None
        rep.ok(f"V2 최신 as_of_month = {latest}  → {as_of_label(latest)}")
    except Exception as exc:
        rep.warn(f"land_basic_stats_v2 분포 조회 실패: {exc!r}")

    # population (DECISIONS D-004 — 전국 적재 확인)
    try:
        with engine.connect() as conn:
            sido_rows = conn.execute(
                text(
                    """
                    SELECT LEFT(beopjungri_code,2) AS sido, COUNT(*) AS n
                      FROM population_jusosagae
                     GROUP BY LEFT(beopjungri_code,2)
                     ORDER BY sido
                    """
                )
            ).all()
        snapshot["population_sido_distinct"] = len(sido_rows)
        rep.ok(f"population_jusosagae 시도 개수 = {len(sido_rows)}")
        if 0 < len(sido_rows) < 17:
            rep.warn(
                "전국이 아니라 일부 시도만 적재된 상태 — DECISIONS D-004 (전국 적재) 확인"
            )
    except Exception as exc:
        rep.warn(f"population_jusosagae 분포 조회 실패: {exc!r}")

    return snapshot


def check_land_tx_duplicates(rep: Report, engine) -> None:
    """TRANSACTION_HASH_DEDUPE — business key 중복·비하동 회귀 샘플 (읽기 only)."""
    rep.section("3b) land_transactions 중복 (6월 dedupe 전 점검)")
    try:
        with engine.connect() as conn:
            extra = conn.execute(
                text(
                    """
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
                )
            ).scalar()
            biha = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM land_transactions lt
                    WHERE lt.beopjungri_code = '4311313800'
                      AND lt.zone_type = '보녹' AND lt.land_category = '답'
                      AND lt.is_valid = TRUE
                    """
                )
            ).scalar()
        extra_i = int(extra or 0)
        biha_i = int(biha or 0)
        if extra_i == 0 and biha_i == 2:
            rep.ok(f"중복 없음, 비하동 보녹·답 = {biha_i}건")
        else:
            rep.warn(
                f"중복 extra_rows≈{extra_i:,}, 비하동 보녹·답={biha_i}건 (dedupe 후 기대: 0, 2) — "
                "docs/TRANSACTION_HASH_DEDUPE.md"
            )
    except Exception as exc:
        rep.warn(f"land_transactions 중복 조회 실패: {exc!r}")


# ---------------------------------------------------------------------------
# 4) SOP §B 명령 dry-run (--help 만)
# ---------------------------------------------------------------------------


SOP_COMMANDS = [
    ("run_pipeline.py", ["--help"]),
    ("build_stats_v2.py", ["--help"]),
    ("dedupe_land_transactions.py", ["--help"]),
    ("seed_population_csv.py", ["--help"]),
    ("verify_v2_national_samples.py", ["--help"]),
    ("verify_monthly_integrity.py", ["--help"]),
]


def check_sop_helps(rep: Report) -> None:
    rep.section("4) SOP §B 명령 dry-run (--help)")
    for script, args in SOP_COMMANDS:
        path = ROOT / script
        if not path.exists():
            rep.err(f"{script} 없음")
            continue
        try:
            res = subprocess.run(
                [PY, str(path), *args],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode == 0:
                rep.ok(f"{script} --help OK")
            else:
                rep.err(
                    f"{script} --help 실패 (rc={res.returncode}): "
                    f"{(res.stderr or res.stdout).strip().splitlines()[:3]}"
                )
        except Exception as exc:
            rep.err(f"{script} 실행 자체 실패: {exc!r}")


# ---------------------------------------------------------------------------
# 5) /health (옵션)
# ---------------------------------------------------------------------------


def check_health(rep: Report, url: str | None) -> None:
    if not url:
        rep.section("5) /health (옵션)")
        rep.info("--health-url 미지정 — 건너뜀")
        return
    rep.section(f"5) GET {url}")
    try:
        import requests  # type: ignore
    except Exception:
        rep.warn("requests 미설치 — /health 점검 생략")
        return
    try:
        r = requests.get(url, timeout=5)  # type: ignore[name-defined]
    except Exception as exc:
        rep.warn(f"백엔드 미기동 또는 통신 실패: {exc!r}")
        return
    rep.ok(f"status = {r.status_code}")
    try:
        body = r.json()
    except Exception:
        rep.warn("JSON 파싱 실패")
        return
    rep.info(json.dumps(body, ensure_ascii=False))
    laom = body.get("latest_as_of_month")
    if laom:
        try:
            d = date.fromisoformat(laom)
            rep.ok(f"latest_as_of_month = {laom}  → {as_of_label(d)}")
        except Exception:
            rep.warn(f"latest_as_of_month 형식 이상: {laom!r}")
    else:
        rep.warn(
            "latest_as_of_month 비어있음 — V2 미적재거나 백엔드 코드가 옛 버전(B4 이전)"
        )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="V2 갱신 SOP §B 리허설 (읽기 전용)."
    )
    parser.add_argument(
        "--health-url",
        default=os.environ.get("REHEARSE_HEALTH_URL", ""),
        help="백엔드 health 엔드포인트(예: http://127.0.0.1:8000/health). 미지정 시 건너뜀.",
    )
    parser.add_argument(
        "--artifact",
        default=str(ARTIFACT_DEFAULT),
        help=f"결과를 저장할 파일 경로 (기본: {ARTIFACT_DEFAULT})",
    )
    args = parser.parse_args()

    rep = Report()
    rep.section("V2 갱신 리허설 시작")
    rep.info(f"repo = {REPO}")
    rep.info(f"python = {sys.version.split()[0]}")

    check_env(rep)
    engine = get_engine()
    check_db_snapshot(rep)
    check_land_tx_duplicates(rep, engine)
    check_sop_helps(rep)
    check_health(rep, args.health_url or None)

    rep.section("결과 요약")
    rep.info(f"errors={rep.errors}  warnings={rep.warnings}")
    if rep.errors == 0:
        rep.ok("리허설 통과 — 실제 §B 실행 가능 상태로 보입니다.")
    else:
        rep.err("에러가 있습니다 — 위 항목을 해결한 뒤 다시 돌리세요.")

    out = Path(args.artifact)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(rep.lines) + "\n", encoding="utf-8")
        print(f"\n아티팩트 저장: {out}")
    except Exception as exc:
        print(f"아티팩트 저장 실패: {exc!r}")

    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
