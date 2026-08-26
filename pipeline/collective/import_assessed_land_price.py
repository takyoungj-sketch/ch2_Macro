"""개별공시지가 정규화 파일 → 집합 단지 대표 필지 mart.

기본 입력은 ``raw/raw addition/개별공시지가(브이월드)`` 아래의 AL_D151 CSV들이다.
원천기관별 포맷에 의존하지 않도록 다음 의미의 열만 필요로 한다.

* PNU: ``PNU``·``필지고유번호``·``고유번호`` 중 하나
* 가격: ``개별공시지가``·``공시지가``·``land_price`` 중 하나
* 연도: ``기준연도``·``공시연도``·``year`` 중 하나

대표 필지는 현재 building_stats의 lot_number/beopjungri_code 조합으로 만들며,
한 단지에 여러 필지가 있어도 building_key별 한 행만 적재한다.

사용 예:
    python -m collective.import_assessed_land_price --input path/to/file.csv
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import bindparam, text

from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy
from parcel_master.pnu import pick_incheon_old_bjd, pnu_from_tx, remap_pnu_bjd

REPO = Path(__file__).resolve().parents[2]
DDL = REPO / "db" / "069_collective_building_assessed_land_price.sql"
DEFAULT_SOURCE_DIR = REPO / "raw" / "raw addition" / "개별공시지가(브이월드)"

_PNU_COLUMNS = ("pnu", "PNU", "필지고유번호", "고유번호")
_PRICE_COLUMNS = (
    "assessed_land_price",
    "land_price",
    "개별공시지가",
    "공시지가",
)
_YEAR_COLUMNS = (
    "assessed_land_price_year",
    "year",
    "기준연도",
    "공시연도",
    "공시년도",
)


def _find_column(columns: pd.Index, candidates: tuple[str, ...]) -> str:
    normalized = {re.sub(r"\s+", "", str(c)).lower(): str(c) for c in columns}
    for candidate in candidates:
        found = normalized.get(re.sub(r"\s+", "", candidate).lower())
        if found:
            return found
    raise ValueError(f"필수 열을 찾지 못했습니다: {', '.join(candidates)}")


def _normalize_pnu(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    raw = str(value).strip().replace(" ", "")
    if raw.endswith(".0"):
        raw = raw[:-2]
    return raw if len(raw) == 19 and raw.isdigit() else None


def _number(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    raw = re.sub(r"[^\d.-]", "", str(value))
    if not raw or raw in {"-", "."}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _source_encoding(path: Path) -> str:
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            pd.read_csv(path, nrows=0, dtype=str, encoding=encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("source", b"", 0, 1, f"지원 인코딩 없음: {path}")


def _read_source_frame(
    path: Path,
    usecols: list[str] | None = None,
    *,
    chunksize: int | None = None,
    nrows: int | None = None,
) -> pd.DataFrame | Any:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str, usecols=usecols, nrows=nrows)
    return pd.read_csv(
        path,
        dtype=str,
        encoding=_source_encoding(path),
        usecols=usecols,
        chunksize=chunksize,
        nrows=nrows,
    )


def _normalize_source_frame(
    frame: pd.DataFrame,
    *,
    target_pnus: set[str] | None = None,
    old_to_current_bjd: dict[str, str] | None = None,
) -> pd.DataFrame:
    pnu_col = _find_column(frame.columns, _PNU_COLUMNS)
    price_col = _find_column(frame.columns, _PRICE_COLUMNS)
    year_col = _find_column(frame.columns, _YEAR_COLUMNS)
    out = pd.DataFrame(
        {
            "pnu": frame[pnu_col].map(_normalize_pnu),
            "assessed_land_price": frame[price_col].map(_number),
            "assessed_land_price_year": frame[year_col].map(_number),
        }
    )
    if old_to_current_bjd:
        out["pnu"] = out["pnu"].map(
            lambda p: remap_pnu_bjd(p, old_to_current_bjd) if p else None
        )
    if target_pnus is not None:
        out = out[out["pnu"].isin(target_pnus)]
    out = out[
        out["pnu"].notna()
        & out["assessed_land_price"].notna()
        & (out["assessed_land_price"] > 0)
        & out["assessed_land_price_year"].notna()
    ].copy()
    out["assessed_land_price_year"] = out["assessed_land_price_year"].astype(int)
    return out.sort_values("assessed_land_price_year").drop_duplicates("pnu", keep="last")


def read_source(
    path: Path,
    *,
    target_pnus: set[str] | None = None,
    old_to_current_bjd: dict[str, str] | None = None,
) -> pd.DataFrame:
    files = (
        [path]
        if path.is_file()
        else sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() == ".csv")
    )
    if not files:
        raise FileNotFoundError(f"공시지가 CSV가 없습니다: {path}")

    records: dict[str, dict[str, Any]] = {}
    for source_file in files:
        print(f"scan={source_file.name}", flush=True)
        header = _read_source_frame(source_file, usecols=None, nrows=0)
        columns = [
            _find_column(header.columns, candidates)
            for candidates in (_PNU_COLUMNS, _PRICE_COLUMNS, _YEAR_COLUMNS)
        ]
        # AL_D151은 대용량이므로 필요한 세 열만 청크로 읽는다.
        chunks = _read_source_frame(source_file, usecols=columns, chunksize=250_000)
        if isinstance(chunks, pd.DataFrame):
            chunks = (chunks,)
        for chunk in chunks:
            normalized = _normalize_source_frame(
                chunk,
                target_pnus=target_pnus,
                old_to_current_bjd=old_to_current_bjd,
            )
            for rec in normalized.to_dict(orient="records"):
                previous = records.get(rec["pnu"])
                if previous is None or rec["assessed_land_price_year"] >= previous["assessed_land_price_year"]:
                    records[rec["pnu"]] = rec
    return pd.DataFrame.from_records(
        list(records.values()),
        columns=["pnu", "assessed_land_price", "assessed_land_price_year"],
    )


def read_source_from_parcel_master(
    target_pnus: set[str],
    *,
    current_to_old_bjd: dict[str, str] | None = None,
) -> pd.DataFrame:
    """parcel_land_price 최신 연도. 거래연도 정합 없음.

    인천 분구처럼 공부는 구 PNU, stats는 신 PNU인 경우 구 PNU로도 조회한 뒤
    결과는 신 PNU 키로 되돌린다.
    """
    from parcel_master.db_utils import get_parcel_engine

    if not target_pnus:
        return pd.DataFrame(columns=["pnu", "assessed_land_price", "assessed_land_price_year"])

    lookup = set(target_pnus)
    old_to_current_pnu: dict[str, str] = {}
    if current_to_old_bjd:
        for current in target_pnus:
            old = remap_pnu_bjd(current, current_to_old_bjd)
            if old and old != current:
                lookup.add(old)
                old_to_current_pnu[old] = current

    eng = get_parcel_engine()
    records: dict[str, dict[str, Any]] = {}
    pnus = sorted(lookup)
    sql = text(
        """
        SELECT DISTINCT ON (pnu)
            pnu, price_per_m2 AS assessed_land_price, price_year AS assessed_land_price_year
        FROM parcel_land_price
        WHERE pnu IN :pnus
        ORDER BY pnu, price_year DESC
        """
    )
    with eng.connect() as conn:
        for i in range(0, len(pnus), 2000):
            chunk = pnus[i : i + 2000]
            stmt = sql.bindparams(bindparam("pnus", expanding=True))
            for row in conn.execute(stmt, {"pnus": chunk}).mappings():
                raw_pnu = str(row["pnu"]).strip()
                pnu = old_to_current_pnu.get(raw_pnu, raw_pnu)
                rec = {
                    "pnu": pnu,
                    "assessed_land_price": float(row["assessed_land_price"]),
                    "assessed_land_price_year": int(row["assessed_land_price_year"]),
                }
                previous = records.get(pnu)
                # 신 PNU가 공부에 있으면 그걸 우선하고, 연도가 같으면 신 코드를 유지한다.
                if previous is None or rec["assessed_land_price_year"] > previous["assessed_land_price_year"]:
                    records[pnu] = rec
                elif (
                    rec["assessed_land_price_year"] == previous["assessed_land_price_year"]
                    and raw_pnu == pnu
                ):
                    records[pnu] = rec
    return pd.DataFrame.from_records(
        list(records.values()),
        columns=["pnu", "assessed_land_price", "assessed_land_price_year"],
    )


def _apply_ddl(engine) -> None:
    with engine.begin() as conn:
        for statement in DDL.read_text(encoding="utf-8").split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))


def _representative_pnus(conn, asset_types: tuple[str, ...]) -> list[dict[str, Any]]:
    statement = text(
        """
        WITH ranked AS (
            SELECT building_key, asset_type, beopjungri_code, lot_number,
                   ROW_NUMBER() OVER (
                       PARTITION BY building_key, asset_type
                       ORDER BY as_of_month DESC, window_years DESC
                   ) AS rn
            FROM collective_building_stats
            WHERE asset_type IN :asset_types
        )
        SELECT building_key, asset_type, beopjungri_code, lot_number
        FROM ranked
        WHERE rn = 1
        """
    ).bindparams(bindparam("asset_types", expanding=True))
    rows = conn.execute(
        statement,
        {"asset_types": list(asset_types)},
    ).mappings()
    out: list[dict[str, Any]] = []
    for row in rows:
        pnu = pnu_from_tx(row["beopjungri_code"], row["lot_number"])
        if pnu:
            out.append(
                {
                    "building_key": str(row["building_key"]).strip(),
                    "asset_type": str(row["asset_type"]).strip(),
                    "pnu": pnu,
                }
            )
    return out


def _gwangju_old_to_current_bjd(conn) -> dict[str, str]:
    rows = conn.execute(
        text(
            """
            SELECT old.beopjungri_code AS old_code,
                   current.beopjungri_code AS current_code
            FROM region_codes old
            JOIN region_codes current
              ON current.sido_code = '12'
             AND COALESCE(current.is_active, TRUE)
             AND current.sigungu_name = old.sigungu_name
             AND current.eupmyeondong_name = old.eupmyeondong_name
             AND current.beopjungri_name = old.beopjungri_name
            WHERE LEFT(TRIM(old.beopjungri_code), 2) IN ('29', '46')
            """
        )
    ).mappings().all()
    mapping = {str(row["old_code"]).strip(): str(row["current_code"]).strip() for row in rows}
    if len(mapping) != len(rows):
        raise RuntimeError("광주·전남 구코드 매핑이 중복되어 중단합니다")
    return mapping


def _incheon_reform_bjd_maps(conn) -> tuple[dict[str, str], dict[str, str]]:
    """인천 분구: 구 PNU ↔ 신 PNU. 동 이름 단독 조인은 쓰지 않는다."""
    rows = conn.execute(
        text(
            """
            SELECT current.beopjungri_code AS current_code,
                   old.beopjungri_code AS old_code
            FROM region_codes current
            JOIN region_codes old
              ON old.sido_code = '28'
             AND old.eupmyeondong_name = current.eupmyeondong_name
             AND old.beopjungri_name = current.beopjungri_name
             AND LEFT(TRIM(old.beopjungri_code), 5) IN ('28260', '28110', '28140')
            WHERE current.sido_code = '28'
              AND LEFT(TRIM(current.beopjungri_code), 5) IN ('28290', '28275', '28155', '28125')
              AND COALESCE(current.is_active, TRUE)
            """
        )
    ).mappings().all()
    grouped: dict[str, list[str]] = {}
    for row in rows:
        current = str(row["current_code"]).strip()
        old = str(row["old_code"]).strip()
        grouped.setdefault(current, []).append(old)

    current_to_old: dict[str, str] = {}
    old_to_current: dict[str, str] = {}
    for current, olds in grouped.items():
        old = pick_incheon_old_bjd(current, olds)
        if not old:
            continue
        current_to_old[current] = old
        previous = old_to_current.get(old)
        if previous is not None and previous != current:
            raise RuntimeError(
                f"인천 구 법정동 {old} 이 {previous} 와 {current} 에 동시에 매핑됩니다"
            )
        old_to_current[old] = current
    return old_to_current, current_to_old


def _reform_bjd_maps(conn) -> tuple[dict[str, str], dict[str, str]]:
    gwangju = _gwangju_old_to_current_bjd(conn)
    incheon_old_to_current, current_to_old = _incheon_reform_bjd_maps(conn)
    overlap = set(gwangju) & set(incheon_old_to_current)
    if overlap:
        sample = ", ".join(sorted(overlap)[:5])
        raise RuntimeError(f"광주·인천 법정동 맵이 겹칩니다: {sample}")
    return {**gwangju, **incheon_old_to_current}, current_to_old


def _old_to_current_bjd(conn) -> dict[str, str]:
    old_to_current, _ = _reform_bjd_maps(conn)
    return old_to_current


def _load_reform_bjd_maps(engine) -> tuple[dict[str, str], dict[str, str]]:
    with engine.connect() as conn:
        old_to_current, current_to_old = _reform_bjd_maps(conn)
    if old_to_current or current_to_old:
        return old_to_current, current_to_old
    land_engine = get_land_engine_for_region_copy()
    with land_engine.connect() as conn:
        return _reform_bjd_maps(conn)


def load(
    engine,
    source: pd.DataFrame,
    asset_types: tuple[str, ...],
    *,
    candidates: list[dict[str, Any]] | None = None,
    source_label: str = "individual_official_land_price",
    current_to_old_bjd: dict[str, str] | None = None,
) -> tuple[int, int]:
    price_by_pnu = source.set_index("pnu").to_dict(orient="index")

    def _price_row(pnu: str) -> dict[str, Any] | None:
        row = price_by_pnu.get(pnu)
        if row is not None:
            return row
        if not current_to_old_bjd:
            return None
        old = remap_pnu_bjd(pnu, current_to_old_bjd)
        if old and old != pnu:
            return price_by_pnu.get(old)
        return None

    if candidates is None:
        with engine.connect() as conn:
            candidates = _representative_pnus(conn, asset_types)
    records = []
    for candidate in candidates:
        price = _price_row(candidate["pnu"])
        if price is None:
            continue
        records.append(
            {
                **candidate,
                "assessed_land_price": price["assessed_land_price"],
                "assessed_land_price_year": price["assessed_land_price_year"],
                "source": source_label,
            }
        )
    if not records:
        return len(candidates), 0
    sql = text(
        """
        INSERT INTO collective_building_assessed_land_price (
            building_key, asset_type, representative_pnu,
            assessed_land_price, assessed_land_price_year, source
        ) VALUES (
            :building_key, :asset_type, :pnu,
            :assessed_land_price, :assessed_land_price_year, :source
        )
        ON CONFLICT (building_key, asset_type) DO UPDATE SET
            representative_pnu = EXCLUDED.representative_pnu,
            assessed_land_price = EXCLUDED.assessed_land_price,
            assessed_land_price_year = EXCLUDED.assessed_land_price_year,
            source = EXCLUDED.source,
            loaded_at = NOW()
        WHERE EXCLUDED.assessed_land_price_year >=
              collective_building_assessed_land_price.assessed_land_price_year
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, records)
    return len(candidates), len(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--dry-run", action="store_true", help="원천 스캔·매칭 예상만 하고 DB에 쓰지 않음")
    parser.add_argument(
        "--from-parcel-master",
        action="store_true",
        help="공부 달: parcel_land_price 최신 연도로 재파생. CSV 대신",
    )
    parser.add_argument(
        "--asset-type",
        action="append",
        dest="asset_types",
        choices=("apartment", "rowhouse", "officetel"),
    )
    args = parser.parse_args()
    asset_types = tuple(args.asset_types or ("apartment", "rowhouse", "officetel"))
    engine = get_collective_engine()
    old_to_current_bjd, current_to_old_bjd = _load_reform_bjd_maps(engine)
    print(
        f"reform_bjd old_to_current={len(old_to_current_bjd):,} "
        f"incheon_current_to_old={len(current_to_old_bjd):,}",
        flush=True,
    )
    with engine.connect() as conn:
        candidates = _representative_pnus(conn, asset_types)
    target_pnus = {row["pnu"] for row in candidates}

    if args.from_parcel_master:
        source = read_source_from_parcel_master(
            target_pnus,
            current_to_old_bjd=current_to_old_bjd,
        )
        source_label = "parcel_land_price"
    else:
        source = read_source(
            args.input,
            target_pnus=target_pnus,
            old_to_current_bjd=old_to_current_bjd,
        )
        source_label = "individual_official_land_price"
    if args.dry_run:
        print(
            f"source_pnu_matched={len(source):,} representative_candidates={len(candidates):,} "
            f"asset_types={','.join(asset_types)} dry_run=true",
            flush=True,
        )
        return

    _apply_ddl(engine)
    candidate_count, loaded = load(
        engine,
        source,
        asset_types,
        candidates=candidates,
        source_label=source_label,
        current_to_old_bjd=current_to_old_bjd,
    )
    print(
        f"source_pnu_matched={len(source):,} representative_candidates={candidate_count:,} "
        f"loaded={loaded:,} asset_types={','.join(asset_types)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
