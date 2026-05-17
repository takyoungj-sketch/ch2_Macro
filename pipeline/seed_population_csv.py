"""
행정안전부 등 「지역별(법정동) 성별 연령별 주민등록 인구수」 CSV를 읽어 population_stats 에 적재한다.

파일 예: 지역별(법정동) 성별 연령별 주민등록 인구수_20221231.csv
  - 헤더: 법정동코드, 기준연월, 시도명, …, 계, 남자, 여자, …
  - 각 행은 법정동 단위이며 「계」 열이 연령 합계 인구이다.

사용법:
    cd pipeline
    python seed_population_csv.py --file ../data/population/지역별(법정동)..._20221231.csv
    python seed_population_csv.py --file ...csv --dry-run
    python seed_population_csv.py --file ...csv --all-sido   # 전국 (주의: 해당 연도·월 행 전량 교체)
"""

from __future__ import annotations

import argparse
import logging
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db_utils import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ADMIN_LEVEL = "beopjungri"


def infer_year_month_from_filename(path: Path) -> tuple[int, int] | None:
    m = re.search(r"_(\d{8})\.csv$", path.name)
    if not m:
        return None
    d = m.group(1)
    return int(d[:4]), int(d[4:6])


def normalize_beopjung_code(raw: object) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        if "e" in s.lower() or "." in s:
            s = str(int(float(s)))
    except (ValueError, OverflowError):
        pass
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return None
    if len(digits) >= 10:
        digits = digits[-10:]
    else:
        digits = digits.zfill(10)
    return digits if len(digits) == 10 else None


def parse_reference_date(series: pd.Series) -> tuple[int, int]:
    """기준연월 열 첫 유효값에서 연·월 추출 (예: 2022-12-31)."""
    for raw in series.dropna().head(50):
        s = str(raw).strip()
        if not s:
            continue
        parts = re.split(r"[-/]", s)
        if len(parts) >= 2 and parts[0].isdigit():
            y, mo = int(parts[0]), int(parts[1])
            if 1900 <= y <= 2100 and 1 <= mo <= 12:
                return y, mo
    raise ValueError("기준연월에서 연·월을 파싱할 수 없습니다.")


def load_population_rows(path: Path) -> tuple[list[dict], int, int, str]:
    encodings = ("utf-8-sig", "cp949", "euc-kr", "utf-8")
    df = None
    last_err: Exception | None = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc, dtype=str)
            log.info("CSV 인코딩: %s", enc)
            break
        except UnicodeDecodeError as e:
            last_err = e
            continue
    if df is None:
        raise ValueError(f"CSV 인코딩 실패 ({path}): {last_err}") from last_err
    cols = {str(c).strip(): c for c in df.columns}
    code_col = cols.get("법정동코드")
    date_col = cols.get("기준연월")
    total_col = cols.get("계")
    if not code_col or not total_col:
        raise ValueError("필수 컬럼 없음: 법정동코드, 계")

    fn_ym = infer_year_month_from_filename(path)
    if fn_ym:
        stats_year, stats_month = fn_ym
    elif date_col is not None:
        stats_year, stats_month = parse_reference_date(df[date_col])
    else:
        raise ValueError("파일명(_YYYYMMDD.csv) 또는 기준연월 컬럼으로 연·월을 알 수 없습니다.")

    rows_out: list[dict] = []
    skipped = 0
    for _, row in df.iterrows():
        code = normalize_beopjung_code(row.get(code_col))
        if not code:
            skipped += 1
            continue
        raw_tot = row.get(total_col)
        if raw_tot is None or (isinstance(raw_tot, float) and pd.isna(raw_tot)):
            skipped += 1
            continue
        try:
            tot = int(str(raw_tot).replace(",", "").strip())
        except ValueError:
            skipped += 1
            continue
        rows_out.append(
            {
                "stats_year": stats_year,
                "stats_month": stats_month,
                "admin_code": code,
                "total_population": tot,
            }
        )

    agg = defaultdict(int)
    for r in rows_out:
        agg[r["admin_code"]] += int(r["total_population"])
    rows_out = [
        {
            "stats_year": stats_year,
            "stats_month": stats_month,
            "admin_code": code,
            "total_population": pop,
        }
        for code, pop in sorted(agg.items())
    ]

    src = path.name[:80]
    return rows_out, stats_year, stats_month, src


def main() -> None:
    parser = argparse.ArgumentParser(description="법정동 인구 CSV → population_stats 적재")
    parser.add_argument("--file", required=True, help="CSV 경로")
    parser.add_argument(
        "--codes-prefix",
        default=None,
        metavar="PREFIX",
        help=(
            "법정동코드 접두 필터 (예: 43=충북, 41=경기). "
            "**미지정·빈 문자 시 전국 적재**(DECISIONS D-004). 시도 한정 시에만 명시."
        ),
    )
    parser.add_argument(
        "--all-sido",
        action="store_true",
        help="(레거시) 접두 필터 비움 — 미지정 기본값과 동일. 호환을 위해 유지.",
    )
    parser.add_argument("--dry-run", action="store_true", help="DB 쓰기 없이 행 수만 출력")
    args = parser.parse_args()

    path = Path(args.file).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"파일 없음: {path}")

    rows, stats_year, stats_month, source_label = load_population_rows(path)
    # DECISIONS D-004: --codes-prefix 미지정 시 전국 적재. --all-sido 는 레거시 동의어.
    raw_prefix = args.codes_prefix if args.codes_prefix is not None else ""
    prefix = "" if args.all_sido else str(raw_prefix).strip()

    filtered = rows
    if prefix:
        filtered = [r for r in rows if str(r["admin_code"]).startswith(prefix)]

    log.info(
        "파싱 완료: 총 %d행 → 접두 '%s' 적용 후 %d행 (%d년 %d월 기준)",
        len(rows),
        prefix or "(전국)",
        len(filtered),
        stats_year,
        stats_month,
    )
    if args.dry_run:
        log.info("dry-run 종료 (skipped 원본 행은 별도 카운트 없음)")
        return

    engine = get_engine()
    insert_stmt = text(
        """
        INSERT INTO population_stats (
            stats_year, stats_month, admin_code, admin_level,
            total_population, source
        ) VALUES (
            :stats_year, :stats_month, :admin_code, :admin_level,
            :total_population, :source
        )
        """
    )

    with engine.begin() as conn:
        if prefix:
            del_stmt = text(
                """
                DELETE FROM population_stats
                WHERE stats_year = :sy
                  AND stats_month = :sm
                  AND admin_level = :al
                  AND btrim(cast(admin_code AS text)) LIKE :pfx
                """
            )
            conn.execute(
                del_stmt,
                {
                    "sy": stats_year,
                    "sm": stats_month,
                    "al": ADMIN_LEVEL,
                    "pfx": f"{prefix}%",
                },
            )
            log.info(
                "기존 행 삭제: 연도=%s 월=%s admin_level=%s 코드 LIKE %s%%",
                stats_year,
                stats_month,
                ADMIN_LEVEL,
                prefix,
            )
        else:
            del_stmt = text(
                """
                DELETE FROM population_stats
                WHERE stats_year = :sy AND stats_month = :sm AND admin_level = :al
                """
            )
            conn.execute(del_stmt, {"sy": stats_year, "sm": stats_month, "al": ADMIN_LEVEL})
            log.warning("전국 모드: 해당 연도·월의 population_stats(beopjungri) 전량 삭제 후 재적재")

        batch = []
        inserted = 0
        chunk = 800
        for r in filtered:
            batch.append(
                {
                    "stats_year": r["stats_year"],
                    "stats_month": r["stats_month"],
                    "admin_code": r["admin_code"],
                    "admin_level": ADMIN_LEVEL,
                    "total_population": r["total_population"],
                    "source": source_label,
                }
            )
            if len(batch) >= chunk:
                conn.execute(insert_stmt, batch)
                inserted += len(batch)
                batch = []
        if batch:
            conn.execute(insert_stmt, batch)
            inserted += len(batch)

    log.info("적재 완료: %d건", inserted)


if __name__ == "__main__":
    main()
