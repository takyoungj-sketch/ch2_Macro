"""Building identity for collective stats aggregation."""

from __future__ import annotations

import csv
import hashlib
import logging
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# 집합 2단계(D-084·Phase A 결정): 다른 단지가 한 이름 키로 묶인 키만 동 단위로 나눈다.
# 목록 밖 키는 기존 문자열 그대로 → 해시 불변.
SPLIT_UNITS_PATH = Path(__file__).resolve().parent / "data" / "p2_split_units.csv"
SPLIT_SUFFIX = "|emd:"

# 분양·입주권(building_key 전용). 원본 building_name / display_name 은 유지.
_PRESALE_KEY_ASSET = "presale"

# 보수적 브랜드 alias — 키 정규화에만 사용
_BRAND_ALIAS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"I[\s\-]?PARK", re.IGNORECASE), "아이파크"),
)

_JE_DANJI_RE = re.compile(r"제(\d+)단지")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(s: str | None) -> str:
    """주소·표시용 가벼운 정규화(공백 축소). 원문 형태를 크게 바꾸지 않음."""
    if not s:
        return ""
    t = str(s).strip()
    t = _WHITESPACE_RE.sub(" ", t)
    return t


def normalize_building_name_for_key(s: str | None, *, asset_type: str) -> str:
    """building_key 에 넣는 단지명.

    분양권만 강한 규칙(공백 제거·영문 브랜드 alias·단지번호).
    그 외 유형은 normalize_name 과 동일(기존 키 호환).
    """
    base = normalize_name(s)
    if not base:
        return ""
    if asset_type != _PRESALE_KEY_ASSET:
        return base
    return _normalize_presale_name_for_key(base)


def _normalize_presale_name_for_key(name: str) -> str:
    t = unicodedata.normalize("NFC", name)
    t = _WHITESPACE_RE.sub("", t)
    for pat, repl in _BRAND_ALIAS_PATTERNS:
        t = pat.sub(repl, t)
    t = _JE_DANJI_RE.sub(r"\1단지", t)
    return t


def _norm_series(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True)


def _sha256_series(raw: pd.Series) -> pd.Series:
    return raw.map(lambda x: hashlib.sha256(x.encode("utf-8")).hexdigest())


def building_key_raw_series(df: pd.DataFrame, asset_type: str) -> pd.Series:
    """attach_building_identity 와 같은 키 원문 문자열(해시 전)."""
    out = df
    a1 = _norm_series(out["addr1"]) if "addr1" in out.columns else pd.Series("", index=out.index)
    a2 = _norm_series(out["addr2"]) if "addr2" in out.columns else pd.Series("", index=out.index)
    a3 = _norm_series(out["addr3"]) if "addr3" in out.columns else pd.Series("", index=out.index)
    a4 = _norm_series(out["addr4"]) if "addr4" in out.columns else pd.Series("", index=out.index)
    lot = _norm_series(out["lot_number"]) if "lot_number" in out.columns else pd.Series("", index=out.index)
    road = _norm_series(out["road_name"]) if "road_name" in out.columns else pd.Series("", index=out.index)
    name = _norm_series(out["building_name"]) if "building_name" in out.columns else pd.Series("", index=out.index)
    if asset_type == _PRESALE_KEY_ASSET:
        name_for_key = name.map(lambda n: normalize_building_name_for_key(n, asset_type=asset_type))
    else:
        name_for_key = name
    has_name = name != ""
    raw_named = asset_type + "|" + a1 + "|" + a2 + "|" + a3 + "|name:" + name_for_key
    raw_unnamed = asset_type + "|" + a1 + "|" + a2 + "|" + a3 + "|" + a4 + "|" + lot + "|" + road
    return raw_named.where(has_name, raw_unnamed)


def split_key_from_raw(raw: str, unit_emd8: str) -> str:
    """분할 대상 키의 동 단위 새 키 = sha256(기존 원문 + '|emd:' + 동 단위 대표 법정동8)."""
    return hashlib.sha256((raw + SPLIT_SUFFIX + unit_emd8).encode("utf-8")).hexdigest()


@lru_cache(maxsize=4)
def load_split_units(path: str | None = None) -> dict[str, tuple[dict[str, str], str]]:
    """base_key → ({법정동8: 조각 대표 법정동8}, 코드 없는 행이 갈 1조각 대표 법정동8).

    decision=split 행만 읽는다. 환경변수 CH2_COLLECTIVE_KEY_SPLIT=0 이면 빈 목록(비상 해제용).
    """
    if os.environ.get("CH2_COLLECTIVE_KEY_SPLIT", "1") == "0":
        return {}
    p = Path(path) if path else SPLIT_UNITS_PATH
    if not p.is_file():
        return {}
    units: dict[str, dict[str, str]] = {}
    part1: dict[str, str] = {}
    with p.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("decision") != "split":
                continue
            bk = row["base_key"]
            units.setdefault(bk, {})[row["emd8"]] = row["unit_emd8"]
            if str(row.get("part")) == "1":
                part1[bk] = row["unit_emd8"]
    return {bk: (m, part1.get(bk) or sorted(m.values())[0]) for bk, m in units.items()}


def resolve_split_unit(units: tuple[dict[str, str], str], emd8: str | None) -> str:
    """행의 법정동8 → 조각 대표 법정동8. 처음 보는 동이면 그 동 자체가 새 조각, 코드 없으면 1조각."""
    m, default = units
    e = (emd8 or "").strip()[:8]
    if not e:
        return default
    return m.get(e, e)


def apply_building_key_split(
    df: pd.DataFrame,
    asset_type: str,
    *,
    split_units: dict[str, tuple[dict[str, str], str]] | None = None,
    code_col: str = "beopjungri_code",
) -> pd.DataFrame:
    """법정동 코드가 붙은 뒤 호출. 분할 목록의 키만 동 단위 새 키로 바꾼다(그 밖은 그대로)."""
    units_all = load_split_units() if split_units is None else split_units
    if not units_all or df.empty or "building_key" not in df.columns:
        return df
    hit = df["building_key"].isin(units_all.keys())
    if not hit.any():
        return df
    out = df.copy()
    sub = out.loc[hit]
    raw = building_key_raw_series(sub, asset_type)
    same = _sha256_series(raw) == sub["building_key"]
    if not same.all():
        log.warning("split: 원문 재현 불일치 %d행 — 키 유지", int((~same).sum()))
    codes = sub[code_col] if code_col in sub.columns else pd.Series("", index=sub.index)
    new_keys = [
        split_key_from_raw(r, resolve_split_unit(units_all[k], "" if c is None or c != c else str(c)))
        if ok else k
        for r, k, c, ok in zip(raw, sub["building_key"], codes, same)
    ]
    out.loc[hit, "building_key"] = new_keys
    return out


def attach_building_identity(df: pd.DataFrame, asset_type: str) -> pd.DataFrame:
    """building_key·display_name 컬럼을 벡터 연산으로 추가.

    display_name / building_name 원문 성격은 유지하고,
    building_key 만 (분양권 시) 정규화된 단지명을 사용한다.
    분할 목록 키는 법정동 코드가 붙은 뒤 apply_building_key_split 으로 나눈다.
    """
    out = df.copy()
    a1 = _norm_series(out["addr1"]) if "addr1" in out.columns else pd.Series("", index=out.index)
    a2 = _norm_series(out["addr2"]) if "addr2" in out.columns else pd.Series("", index=out.index)
    a3 = _norm_series(out["addr3"]) if "addr3" in out.columns else pd.Series("", index=out.index)
    a4 = _norm_series(out["addr4"]) if "addr4" in out.columns else pd.Series("", index=out.index)
    lot = _norm_series(out["lot_number"]) if "lot_number" in out.columns else pd.Series("", index=out.index)
    road = _norm_series(out["road_name"]) if "road_name" in out.columns else pd.Series("", index=out.index)
    name = _norm_series(out["building_name"]) if "building_name" in out.columns else pd.Series("", index=out.index)

    if asset_type == _PRESALE_KEY_ASSET:
        name_for_key = name.map(lambda n: normalize_building_name_for_key(n, asset_type=asset_type))
    else:
        name_for_key = name

    has_name = name != ""
    raw_named = asset_type + "|" + a1 + "|" + a2 + "|" + a3 + "|name:" + name_for_key
    raw_unnamed = (
        asset_type + "|" + a1 + "|" + a2 + "|" + a3 + "|" + a4 + "|" + lot + "|" + road
    )
    out["building_key"] = _sha256_series(raw_named.where(has_name, raw_unnamed))

    addr3_lot = (a3 + " " + lot).str.strip()
    out["display_name"] = name.where(
        has_name,
        addr3_lot.where(addr3_lot != "", road).replace("", "(주소 미상)"),
    )
    return out


def derive_display_name(
    *,
    building_name: str | None,
    addr3: str | None,
    lot_number: str | None,
    road_name: str | None,
) -> str:
    name = normalize_name(building_name)
    if name:
        return name
    parts = [normalize_name(addr3), normalize_name(lot_number)]
    label = " ".join(p for p in parts if p)
    if label:
        return label
    return normalize_name(road_name) or "(주소 미상)"


def derive_building_key(
    *,
    asset_type: str,
    addr1: str | None,
    addr2: str | None,
    addr3: str | None,
    addr4: str | None,
    building_name: str | None,
    lot_number: str | None,
    road_name: str | None,
) -> str:
    a1 = normalize_name(addr1)
    a2 = normalize_name(addr2)
    a3 = normalize_name(addr3)
    a4 = normalize_name(addr4)
    name = normalize_building_name_for_key(building_name, asset_type=asset_type)
    if name:
        raw = f"{asset_type}|{a1}|{a2}|{a3}|name:{name}"
    else:
        raw = "|".join(
            [
                asset_type,
                a1,
                a2,
                a3,
                a4,
                normalize_name(lot_number),
                normalize_name(road_name),
            ]
        )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 집합 2단계 C-2: 같은 법정동 안 동명 다른 건물(본번·건축년도) 분할
# ---------------------------------------------------------------------------
# 판정 파일(C-01 의 p2_split_units.csv 와 같은 방식). 열:
#   base_key, asset_type, beopjungri_code(10), main_lot, building_year, part, decision
#   decision=split: 그 (키·법정동) 의 본번 조각. part 0 = 본 조각(키 유지), 1.. = 새 키.
#   decision=keep : 판정 결과 유지(조각 열 비움). 월간 경고 검사의 「판정 끝남」 목록으로만 쓴다.
# 본번이 들어 있으므로 파일을 저장소에 둘지(지번 취급)는 T·Codex 결정 — 경로는 환경변수로 바꿀 수 있다.
SPLIT_UNITS_C2_PATH = Path(__file__).resolve().parent / "data" / "p2_split_units_c2.csv"
C2_SUFFIX = "|c2:"
C2_ENV_OFF = "CH2_COLLECTIVE_KEY_SPLIT_C2"
C2_ENV_PATH = "CH2_COLLECTIVE_KEY_SPLIT_C2_PATH"
C2_MIN_TX = 3


def main_lot_of(lot: object) -> str:
    """지번 → 본번 문자열('123-4' → '123', '0123' → '123'). 비면 ''."""
    if lot is None or (isinstance(lot, float) and lot != lot):
        return ""
    s = str(lot).strip().split("-", 1)[0].strip()
    return str(int(s)) if s.isdigit() else s


def _lot_num(m: str) -> int | None:
    return int(m) if m.isdigit() else None


def _year(y: object) -> int | None:
    if y is None or (isinstance(y, float) and y != y) or str(y).strip() == "":
        return None
    try:
        return int(float(y))
    except (TypeError, ValueError):
        return None


def load_split_units_c2(path: str | Path | None = None) -> dict[str, dict[str, list[tuple[str, int | None, int]]]]:
    """base_key → {법정동10: [(본번, 건축년도, 조각 번호)]}. decision=split 행만. 비상 해제·파일 없음이면 {}."""
    if os.environ.get(C2_ENV_OFF, "1") == "0":
        return {}
    p = Path(path or os.environ.get(C2_ENV_PATH) or SPLIT_UNITS_C2_PATH)
    if not p.is_file():
        return {}
    out: dict[str, dict[str, list[tuple[str, int | None, int]]]] = {}
    with p.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("decision") != "split":
                continue
            out.setdefault(row["base_key"], {}).setdefault(str(row["beopjungri_code"]).strip(), []).append(
                (main_lot_of(row["main_lot"]), _year(row.get("building_year")), int(row["part"])))
    return out


def judged_keys_c2(path: str | Path | None = None) -> set[str]:
    """C-2 판정이 끝난 키(분할·유지 모두). 월간 경고 검사에서 뺄 목록."""
    p = Path(path or os.environ.get(C2_ENV_PATH) or SPLIT_UNITS_C2_PATH)
    if not p.is_file():
        return set()
    with p.open(encoding="utf-8", newline="") as f:
        return {r["base_key"] for r in csv.DictReader(f) if r.get("decision") in ("split", "keep")}


def resolve_c2_part(frags: list[tuple[str, int | None, int]], main_lot: str, year: int | None,
                    n_lot_total: int) -> tuple[str, bool]:
    """행 하나의 C-2 조각 라벨과 「확인 필요」 여부.

    1) 판정 파일에 있는 본번 → 그 조각
    2) 처음 보는 본번: 같은 건축년도 조각이 있으면 그 조각(여럿이면 본번이 가장 가까운 것)
    3) 없고 그 본번 거래(이번 배치 + 기존 원장)가 3건 이상 → 새 조각(라벨 m<본번>, 매달 같은 키)
    4) 3건 미만 → 본번이 가장 가까운 조각에 붙이고 확인 필요
    라벨: 'p<n>' = 판정 파일 조각, 'm<본번>' = 적재 때 생긴 조각. 'p0' 은 본 조각(키 유지).
    """
    for m, _y, part in frags:
        if m == main_lot:
            return f"p{part}", False

    def nearest(cands):
        x = _lot_num(main_lot)
        if x is None:
            return min(cands, key=lambda f: f[2])
        return min(cands, key=lambda f: (abs((_lot_num(f[0]) if _lot_num(f[0]) is not None else 10**9) - x), f[2]))

    same = [f for f in frags if year is not None and f[1] == year]
    if same:
        return f"p{nearest(same)[2]}", False
    if n_lot_total >= C2_MIN_TX:
        return f"m{main_lot}", False
    return f"p{nearest(frags)[2]}", True


def _key_raw_for(raw_base: str, key: str, c01_units: dict) -> str | None:
    """현재 키(C-01 반영 뒤)의 원문. C-01 분할 키면 '|emd:' 접미까지 재현. 재현 못 하면 None."""
    if hashlib.sha256(raw_base.encode("utf-8")).hexdigest() == key:
        return raw_base
    base = hashlib.sha256(raw_base.encode("utf-8")).hexdigest()
    if base in c01_units:
        m, _default = c01_units[base]
        for unit in set(m.values()) | {_default}:
            r = raw_base + SPLIT_SUFFIX + unit
            if hashlib.sha256(r.encode("utf-8")).hexdigest() == key:
                return r
    return None


def c2_key(raw: str, label: str) -> str:
    return hashlib.sha256((raw + C2_SUFFIX + label).encode("utf-8")).hexdigest()


def apply_building_key_split_c2(
    df: pd.DataFrame,
    asset_type: str,
    *,
    units: dict | None = None,
    c01_units: dict | None = None,
    existing_counts: dict[tuple[str, str, str], int] | None = None,
    code_col: str = "beopjungri_code",
) -> pd.DataFrame:
    """C-01 분할(apply_building_key_split) 뒤에 호출. C-2 판정 키의 그 법정동 행만 본번·건축년도로 조각을 정한다.

    - 판정 목록 밖 키, 목록 키의 다른 법정동 행, 본 조각(p0) 행은 키 그대로.
    - 분양권은 대상이 아니다(블록 지번).
    - existing_counts: (키, 법정동10, 본번) → 기존 원장 거래 수(처음 보는 본번의 3건 판정용). 없으면 이번 배치만 센다.
    - 확인 필요 행은 df.attrs['c2_review'] 에 (키, 법정동10, 행 수) 요약으로 남긴다(지번은 남기지 않음).
    """
    units = load_split_units_c2() if units is None else units
    if not units or df.empty or "building_key" not in df.columns or asset_type == _PRESALE_KEY_ASSET:
        return df
    codes = df[code_col].astype(str).str.strip().str[:10] if code_col in df.columns else pd.Series("", index=df.index)
    hit = pd.Series([c in units.get(k, {}) for k, c in zip(df["building_key"], codes)], index=df.index, dtype=bool)
    if not hit.any():
        return df
    c01 = load_split_units() if c01_units is None else c01_units
    out = df.copy()
    sub = out.loc[hit]
    raw_base = building_key_raw_series(sub, asset_type)
    lots = (sub["lot_number"] if "lot_number" in sub.columns else pd.Series("", index=sub.index)).map(main_lot_of)
    years = (sub["building_year"] if "building_year" in sub.columns else pd.Series(None, index=sub.index)).map(_year)
    sub_codes = codes.loc[hit]
    batch_n = pd.Series(1, index=sub.index).groupby([sub["building_key"], sub_codes, lots]).transform("sum")
    existing_counts = existing_counts or {}
    new_keys, review = [], {}
    bad = 0
    for idx, k, c, m, y, rb, bn in zip(sub.index, sub["building_key"], sub_codes, lots, years, raw_base, batch_n):
        label, need = resolve_c2_part(units[k][c], m, y, int(bn) + int(existing_counts.get((k, c, m), 0)))
        if label == "p0":
            new_keys.append(k)
        else:
            raw = _key_raw_for(rb, k, c01)
            if raw is None:
                bad += 1
                new_keys.append(k)
                continue
            new_keys.append(c2_key(raw, label))
        if need:
            review[(k, c)] = review.get((k, c), 0) + 1
    if bad:
        log.warning("c2 split: 원문 재현 불일치 %d행 — 키 유지", bad)
    out.loc[hit, "building_key"] = new_keys
    out.attrs["c2_review"] = [{"building_key": k, "beopjungri_code": c, "rows": n} for (k, c), n in review.items()]
    return out
