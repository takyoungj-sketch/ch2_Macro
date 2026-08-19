"""위치 블록 enrichment — AL_D155 용도지역·인구·임대."""

from __future__ import annotations

import glob
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

log = logging.getLogger(__name__)

# 용도지역 코드 (AL_D155 충북·대전 전량 실측 2026-08-20):
#   UQA1xx 주거 · UQA2xx 상업 · UQA3xx 공업 · UQA4xx 녹지 · UQB1/2/300 관리 · UQC001 농림 · UQD001 자연환경보전
#   UQA001 은 상위 라벨 '도시지역' — 같은 필지에 세부 행과 함께 붙으므로 집계 때 후순위(_COARSE_ZONE_CODES)
# UQQ(지구단위·성장관리) · UQS(도로) · UQT(녹지시설) · UQM(취락지구) · UQW(하천) 등은 용도지구·구역·시설이라 제외한다.
# 개발제한구역은 UDV100 으로 UQ 체계 밖 — 용도구역이라 여기서 다루지 않는다.
_UQA_RE = re.compile(r"^UQ[ABCD]\d+", re.IGNORECASE)
_COARSE_ZONE_CODES = frozenset({"UQA001"})  # app.collective.new_apt.constants.COARSE_UQA_CODES 와 동일
_LOT_NORM = re.compile(r"^(\d+)(?:-(\d+))?$")


def norm_lot(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    t = str(value).strip().replace(" ", "").rstrip("-")
    m = _LOT_NORM.match(t)
    if not m:
        return ""
    main, sub = m.group(1), m.group(2)
    return f"{int(main)}-{int(sub)}" if sub else f"{int(main)}"


def discover_ald155_dirs(raw_root: Path) -> list[Path]:
    patterns = [
        raw_root / "토이계" / "AL_D155_30_*",
        raw_root / "토이계" / "AL_D155_43_*",
        raw_root / "raw addition" / "AL_D155_30_*",
        raw_root / "raw addition" / "AL_D155_43_*",
    ]
    out: list[Path] = []
    for pat in patterns:
        out.extend(Path(p) for p in glob.glob(str(pat)) if Path(p).is_dir())
    return sorted(set(out))


def _read_ald155_chunks(
    csv: Path,
    usecols: list[str],
    chunksize: int,
    keep_keys: set[str] | None = None,
) -> list[pd.DataFrame]:
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        frames: list[pd.DataFrame] = []
        try:
            for chunk in pd.read_csv(
                csv,
                usecols=lambda c: c in usecols,
                chunksize=chunksize,
                encoding=enc,
            ):
                chunk = chunk.rename(
                    columns={
                        "법정동코드": "beopjungri_code",
                        "지번": "lot_number_raw",
                        "용도지역지구코드": "uqa_code",
                        "용도지역지구명": "uqa_label",
                    }
                )
                if "uqa_code" not in chunk.columns:
                    continue
                chunk["uqa_code"] = chunk["uqa_code"].astype(str)
                chunk = chunk[chunk["uqa_code"].str.match(_UQA_RE, na=False)]
                if chunk.empty:
                    continue
                chunk["lot_number"] = chunk["lot_number_raw"].map(norm_lot)
                chunk["beopjungri_code"] = chunk["beopjungri_code"].astype(str).str.zfill(10)
                if keep_keys is not None:
                    keys = chunk["beopjungri_code"] + "|" + chunk["lot_number"]
                    chunk = chunk[keys.isin(keep_keys)]
                    if chunk.empty:
                        continue
                frames.append(chunk[["beopjungri_code", "lot_number", "uqa_code", "uqa_label"]])
            return frames
        except UnicodeDecodeError as exc:
            last_err = exc
            continue
    if last_err:
        raise last_err
    return []


def load_ald155_uqa(
    path: Path,
    *,
    chunksize: int = 200_000,
    keep_lots: set[tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """AL_D155 CSV에서 용도지역 행만 추출. keep_lots가 있으면 해당 지번만 남긴다.

    도시지역 세부(UQA)뿐 아니라 관리지역(UQB)·농림지역(UQC)·자연환경보전지역(UQD)도 포함한다.
    """
    usecols = ["법정동코드", "지번", "용도지역지구코드", "용도지역지구명"]
    frames: list[pd.DataFrame] = []
    csvs = sorted(path.glob("*.csv"))
    if not csvs:
        return pd.DataFrame(columns=["beopjungri_code", "lot_number", "uqa_code", "uqa_label"])
    keep_keys = {f"{code}|{lot}" for code, lot in keep_lots} if keep_lots is not None else None
    for csv in csvs:
        if "head" in csv.name.lower():
            continue
        frames.extend(_read_ald155_chunks(csv, usecols, chunksize, keep_keys=keep_keys))
    if not frames:
        return pd.DataFrame(columns=["beopjungri_code", "lot_number", "uqa_code", "uqa_label"])
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates(subset=["beopjungri_code", "lot_number", "uqa_code"])


def resolve_uqa_for_buildings(
    buildings: pd.DataFrame,
    ald155: pd.DataFrame,
) -> pd.DataFrame:
    """beopjungri+lot exact join → 단지별 용도지역 (다중이면 행수 최빈).

    상위 라벨 '도시지역'(UQA001)은 세부 용도지역이 함께 있으면 후순위다. 최빈값만 보면
    상위 라벨이 세부를 덮어 용도지역이 사실상 도시지역/미상 이분형이 된다.
    """
    if buildings.empty:
        return buildings
    work = buildings.copy()
    work["lot_number"] = work["lot_number"].map(norm_lot)
    work["beopjungri_code"] = work["beopjungri_code"].astype(str)

    merged = work.merge(
        ald155,
        on=["beopjungri_code", "lot_number"],
        how="left",
    )
    if merged.empty:
        work["uqa_code"] = None
        work["uqa_label"] = None
        work["zone_resolution"] = "missing"
        return work

    rows: list[dict] = []
    for bk, group in merged.groupby("building_key"):
        sub = group.dropna(subset=["uqa_code"])
        if sub.empty:
            rows.append(
                {
                    "building_key": bk,
                    "uqa_code": None,
                    "uqa_label": None,
                    "zone_resolution": "missing",
                }
            )
            continue
        specific = sub[~sub["uqa_code"].astype(str).str.upper().isin(_COARSE_ZONE_CODES)]
        coarse_only = specific.empty
        pick_from = sub if coarse_only else specific
        vc = pick_from["uqa_code"].value_counts()
        if coarse_only:
            resolution = "coarse_only"
        else:
            resolution = "mixed" if len(vc) > 1 else "exact"
        top = vc.index[0]
        label = pick_from.loc[pick_from["uqa_code"] == top, "uqa_label"].iloc[0]
        rows.append(
            {
                "building_key": bk,
                "uqa_code": top,
                "uqa_label": label,
                "zone_resolution": resolution,
            }
        )
    picked = pd.DataFrame(rows)
    return work.merge(picked, on="building_key", how="left")


@dataclass
class Ald155PilotReport:
    pilot_sido_codes: list[str]
    n_buildings: int = 0
    n_with_lot: int = 0
    n_uqa_matched: int = 0
    n_mixed_zone: int = 0
    n_land_p50: int = 0
    n_land_cell_lt15: int = 0
    coverage_pct: float = 0.0
    mixed_pct: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pilot_sido_codes": self.pilot_sido_codes,
            "n_buildings": self.n_buildings,
            "n_with_lot": self.n_with_lot,
            "n_uqa_matched": self.n_uqa_matched,
            "n_mixed_zone": self.n_mixed_zone,
            "n_land_p50": self.n_land_p50,
            "n_land_cell_lt15": self.n_land_cell_lt15,
            "coverage_pct": round(self.coverage_pct, 2),
            "mixed_pct": round(self.mixed_pct, 2),
            "notes": self.notes,
        }


def load_apartment_buildings(engine: Engine, *, sido_codes: list[str] | None = None) -> pd.DataFrame:
    clause = ""
    params: dict[str, Any] = {}
    if sido_codes:
        clause = "AND LEFT(beopjungri_code, 2) = ANY(:sido_codes)"
        params["sido_codes"] = sido_codes
    sql = f"""
        SELECT building_key,
               MAX(beopjungri_code) AS beopjungri_code,
               MAX(lot_number) AS lot_number,
               MAX(sigungu_code) AS sigungu_code,
               MAX(display_name) AS display_name
        FROM collective_transactions
        WHERE is_valid = true AND asset_type = 'apartment'
          AND beopjungri_code IS NOT NULL
          {clause}
        GROUP BY building_key
    """
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def fetch_land_p50_for_zones(
    land_engine: Engine,
    *,
    as_of_month,
    window_years: int,
    eup_code: str,
    zone_label: str,
) -> tuple[float | None, int | None]:
    sql = text(
        """
        SELECT median, count
        FROM land_upper_stats_v2
        WHERE region_level = 'eupmyeondong'
          AND region_code = :eup
          AND as_of_month = :as_of
          AND window_years = :wy
          AND zone_type = :zone
          AND land_category = '대'
        LIMIT 1
        """
    )
    with land_engine.connect() as conn:
        row = conn.execute(
            sql,
            {
                "eup": eup_code[:8],
                "as_of": as_of_month,
                "wy": window_years,
                "zone": zone_label,
            },
        ).mappings().first()
    if not row:
        return None, None
    return (
        float(row["median"]) if row["median"] is not None else None,
        int(row["count"]) if row["count"] is not None else None,
    )


def run_ald155_pilot(
    collective_engine: Engine,
    raw_root: Path,
    *,
    land_engine: Engine | None = None,
    as_of_month=None,
    window_years: int = 5,
    output_json: Path | None = None,
) -> Ald155PilotReport:
    dirs = discover_ald155_dirs(raw_root)
    sido_codes = sorted({d.name.split("_")[1][:2] for d in dirs if "AL_D155_" in d.name})
    report = Ald155PilotReport(pilot_sido_codes=sido_codes)
    if not dirs:
        report.notes.append("AL_D155 원본 디렉터리 없음 — raw/토이계/AL_D155_30_* · 43_* 확인")
        if output_json:
            output_json.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    ald = pd.concat([load_ald155_uqa(d) for d in dirs], ignore_index=True)
    bld = load_apartment_buildings(collective_engine, sido_codes=sido_codes or None)
    report.n_buildings = len(bld)
    report.n_with_lot = int(bld["lot_number"].notna().sum())
    resolved = resolve_uqa_for_buildings(bld, ald)
    report.n_uqa_matched = int(resolved["uqa_code"].notna().sum())
    report.n_mixed_zone = int((resolved["zone_resolution"] == "mixed").sum())
    if report.n_buildings:
        report.coverage_pct = 100.0 * report.n_uqa_matched / report.n_buildings
        report.mixed_pct = 100.0 * report.n_mixed_zone / max(report.n_uqa_matched, 1)

    if land_engine is not None and as_of_month is not None:
        land_hits = 0
        thin = 0
        for _, row in resolved[resolved["uqa_code"].notna()].iterrows():
            eup = str(row["beopjungri_code"])[:8]
            zone = str(row["uqa_label"])
            med, cnt = fetch_land_p50_for_zones(
                land_engine,
                as_of_month=as_of_month,
                window_years=window_years,
                eup_code=eup,
                zone_label=zone,
            )
            if med is not None:
                land_hits += 1
            if cnt is not None and cnt < 15:
                thin += 1
        report.n_land_p50 = land_hits
        report.n_land_cell_lt15 = thin

    report.notes.append(
        "아파트 지번 exact join — 용도지역(UQA·UQB 관리·UQC 농림·UQD 자연환경보전), 상위 '도시지역'은 후순위"
    )
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report
