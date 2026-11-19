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
# 판정은 집합 DB 표 collective_building_key_c2_units 에 둔다(본번이 들어 있어 저장소 파일로 두지 않음 — T 결정 2026-11-14).
#   base_key, asset_type, beopjungri_code(10), main_lot, building_year, part, decision, source, decided_at, note
#   decision=split: 그 (키·법정동) 의 본번 조각. part 0 = 본 조각(가장 큰 그룹, 옛 키 유지), 1.. = 새 키.
#   decision=keep : 판정 결과 유지(본번 열 ''). 월간 경고 검사의 「판정 끝남」 목록으로만 쓴다.
C2_TABLE = "collective_building_key_c2_units"
C2_DDL = """
CREATE TABLE IF NOT EXISTS collective_building_key_c2_units (
    base_key        varchar(64) NOT NULL,
    asset_type      varchar(16) NOT NULL,
    beopjungri_code varchar(10) NOT NULL,
    main_lot        varchar(16) NOT NULL DEFAULT '',
    building_year   integer,
    part            integer,
    decision        varchar(8)  NOT NULL CHECK (decision IN ('split', 'keep')),
    source          varchar(32),
    decided_at      timestamptz NOT NULL DEFAULT now(),
    note            text,
    PRIMARY KEY (base_key, beopjungri_code, main_lot),
    CHECK (decision = 'keep' OR (part IS NOT NULL AND main_lot <> ''))
)
"""
C2_SUFFIX = "|c2:"
C2_ENV_OFF = "CH2_COLLECTIVE_KEY_SPLIT_C2"
C2_MIN_TX = 3

C2Units = dict[str, dict[str, list[tuple[str, "int | None", int]]]]


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


def units_from_rows(rows) -> C2Units:
    """(base_key, beopjungri_code, main_lot, building_year, part, decision) 행들 → base_key → {법정동10: [(본번, 연도, 조각)]}."""
    out: C2Units = {}
    for base_key, bjd, main_lot, year, part, decision in rows:
        if decision != "split":
            continue
        out.setdefault(str(base_key), {}).setdefault(str(bjd).strip()[:10], []).append(
            (main_lot_of(main_lot), _year(year), int(part)))
    return out


def c2_table_state(conn) -> tuple[str, int]:
    """('missing' | 'empty' | 'ok', 판정 행 수)."""
    from sqlalchemy import text

    if not conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{C2_TABLE}"}).scalar():
        return "missing", 0
    n = int(conn.execute(text(f"SELECT count(*) FROM {C2_TABLE}")).scalar() or 0)
    return ("ok" if n else "empty"), n


def load_split_units_c2(conn) -> C2Units:
    """집합 DB 의 C-2 판정 표에서 decision=split 행. 비상 해제(CH2_COLLECTIVE_KEY_SPLIT_C2=0)·표 없음이면 {}."""
    if os.environ.get(C2_ENV_OFF, "1") == "0" or conn is None:
        return {}
    from sqlalchemy import text

    if c2_table_state(conn)[0] != "ok":
        return {}
    return units_from_rows(conn.execute(text(
        f"SELECT base_key, beopjungri_code, main_lot, building_year, part, decision FROM {C2_TABLE} "
        "WHERE decision = 'split'")).all())


def judged_keys_c2(conn) -> set[str]:
    """C-2 판정이 끝난 키(분할·유지 모두). 월간 경고 검사에서 뺄 목록. 표가 없으면 빈 집합."""
    from sqlalchemy import text

    if conn is None or c2_table_state(conn)[0] == "missing":
        return set()
    return {str(r[0]) for r in conn.execute(text(f"SELECT DISTINCT base_key FROM {C2_TABLE}"))}


NEW_PART = "new"
C2_AUTO_SOURCE = "auto_ingest"


def resolve_c2_part(frags: list[tuple[str, int | None, int]], main_lot: str, year: int | None,
                    n_lot_total: int) -> tuple[str, bool]:
    """행 하나의 C-2 조각 라벨과 「확인 필요」 여부.

    1) 판정 표에 있는 본번(사람 판정·자동 등록 모두) → 그 조각
    2) 처음 보는 본번: 같은 건축년도 조각이 있으면 그 조각(여럿이면 본번이 가장 가까운 것)
    3) 없고 그 본번 거래(이번 배치 + 기존 원장: 본 키와 모든 파생 조각 키)가 3건 이상 → NEW_PART(새 조각을 만들어 표에 등록)
    4) 3건 미만 → 본번이 가장 가까운 조각에 붙이고 확인 필요
    라벨은 'p<조각 번호>'. 'p0' 은 본 조각(가장 큰 그룹, 옛 키 유지).
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
        return NEW_PART, False
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


def c2_derived_keys(raw: str, units_for_key: dict[str, list[tuple]]) -> set[str]:
    """한 base_key 의 모든 파생 조각 키(p0 제외). 기존 거래 수를 셀 때 본 키와 함께 센다."""
    parts = {f[2] for frags in units_for_key.values() for f in frags if f[2] != 0}
    return {c2_key(raw, f"p{n}") for n in parts}


def apply_building_key_split_c2(
    df: pd.DataFrame,
    asset_type: str,
    *,
    units: C2Units | None = None,
    c01_units: dict | None = None,
    existing_counts: dict[tuple[str, str, str], int] | None = None,
    code_col: str = "beopjungri_code",
) -> pd.DataFrame:
    """C-01 분할(apply_building_key_split) 뒤에 호출. C-2 판정 키의 그 법정동 행만 본번·건축년도로 조각을 정한다.

    - units: load_split_units_c2(conn) 결과(집합 DB 판정 표). 비거나 None 이면 그대로 돌려준다(호출자의 dict 는 바꾸지 않음).
    - 판정 목록 밖 키, 목록 키의 다른 법정동 행, 본 조각(p0) 행은 키 그대로. 분양권은 대상이 아니다.
    - existing_counts: (base_key, 법정동10, 본번) → 기존 원장 거래 수(본 키 + 모든 파생 조각 키 합). 없으면 이번 배치만 센다.
    - 새 조각: 그 (키·법정동)의 조각 번호 최대값 + 1 을 배정하고 df.attrs['c2_new_parts'] 에 등록할 행으로 남긴다.
      호출자(apply_c2_split_from_db)가 판정 표에 출처 C2_AUTO_SOURCE 로 저장 → 다음 달은 표를 기준으로 같은 조각에 배정된다.
    - 확인 필요 행은 df.attrs['c2_review'] 에 (키, 법정동10, 행 수) 요약(지번 없음).
    """
    if not units or df.empty or "building_key" not in df.columns or asset_type == _PRESALE_KEY_ASSET:
        return df
    codes = df[code_col].astype(str).str.strip().str[:10] if code_col in df.columns else pd.Series("", index=df.index)
    hit = pd.Series([c in units.get(k, {}) for k, c in zip(df["building_key"], codes)], index=df.index, dtype=bool)
    if not hit.any():
        return df
    work = {k: {c: list(fr) for c, fr in v.items()} for k, v in units.items()}   # 이번 배치 안에서 새 조각을 더해 간다
    c01 = load_split_units() if c01_units is None else c01_units
    out = df.copy()
    sub = out.loc[hit]
    raw_base = building_key_raw_series(sub, asset_type)
    lots = (sub["lot_number"] if "lot_number" in sub.columns else pd.Series("", index=sub.index)).map(main_lot_of)
    years = (sub["building_year"] if "building_year" in sub.columns else pd.Series(None, index=sub.index)).map(_year)
    sub_codes = codes.loc[hit]
    batch_n = pd.Series(1, index=sub.index).groupby([sub["building_key"], sub_codes, lots]).transform("sum")
    existing_counts = existing_counts or {}
    new_keys, review, new_parts = [], {}, []
    bad = 0
    for k, c, m, y, rb, bn in zip(sub["building_key"], sub_codes, lots, years, raw_base, batch_n):
        frags = work[k][c]
        label, need = resolve_c2_part(frags, m, y, int(bn) + int(existing_counts.get((k, c, m), 0)))
        if label == NEW_PART:
            part = max(f[2] for fr in work[k].values() for f in fr) + 1
            frags.append((m, y, part))
            new_parts.append({"base_key": k, "asset_type": asset_type, "beopjungri_code": c, "main_lot": m,
                              "building_year": y, "part": part, "decision": "split", "source": C2_AUTO_SOURCE})
            label = f"p{part}"
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
    out.attrs["c2_new_parts"] = new_parts
    return out


def existing_main_lot_counts(conn, key_groups: dict[str, set[str]]) -> dict[tuple[str, str, str], int]:
    """(base_key, 법정동10, 본번) → 기존 원장 거래 수. base_key 와 그 파생 조각 키(key_groups[base])를 모두 센다."""
    owner = {k: base for base, ks in key_groups.items() for k in ({base} | set(ks))}
    if not owner:
        return {}
    from sqlalchemy import bindparam, text

    rows = conn.execute(text(
        "SELECT building_key, left(beopjungri_code, 10), split_part(btrim(lot_number), '-', 1), count(*) "
        "FROM collective_transactions WHERE building_key IN :k AND coalesce(btrim(lot_number), '') <> '' "
        "GROUP BY 1, 2, 3").bindparams(bindparam("k", expanding=True)), {"k": sorted(owner)}).all()
    out: dict[tuple[str, str, str], int] = {}
    for k, c, m, n in rows:
        key = (owner[str(k)], str(c), main_lot_of(m))
        out[key] = out.get(key, 0) + int(n)
    return out


def register_c2_parts(conn, parts: list[dict]) -> list[dict]:
    """적재 때 생긴 새 조각을 판정 표에 자동 등록 행(source=auto_ingest)으로 저장.
    이미 있는 (키·법정동·본번)은 DO NOTHING — 그 경우 표의 실제 값(조각 번호)을 다시 읽어 돌려준다.
    반환: 등록 시도한 행마다 {..., "registered": bool, "actual_part": 표에 있는 조각 번호}."""
    if not parts:
        return []
    from sqlalchemy import text

    out = []
    for r in parts:
        got = conn.execute(text(
            f"INSERT INTO {C2_TABLE} (base_key, asset_type, beopjungri_code, main_lot, building_year, part, decision, source, note) "
            "VALUES (:base_key, :asset_type, :beopjungri_code, :main_lot, :building_year, :part, :decision, :source, "
            "'월간 적재 자동 등록 — 판정 검토 대상') ON CONFLICT (base_key, beopjungri_code, main_lot) DO NOTHING "
            "RETURNING part"), r).scalar()
        if got is not None:
            out.append({**r, "registered": True, "actual_part": int(got)})
            continue
        actual = conn.execute(text(
            f"SELECT part, decision FROM {C2_TABLE} WHERE base_key = :base_key AND beopjungri_code = :beopjungri_code "
            "AND main_lot = :main_lot"), r).one_or_none()
        out.append({**r, "registered": False,
                    "actual_part": None if actual is None or actual[0] is None else int(actual[0]),
                    "actual_decision": None if actual is None else actual[1]})
    return out


def _lock_c2_keys(conn, keys: list[str]) -> None:
    """base_key 단위 advisory lock(트랜잭션 끝까지). 정렬된 순서로 잡아 교착을 피한다.
    같은 키를 동시에 적재하는 두 실행이 같은 조각 번호(최대+1)를 따로 배정하지 않게 한다."""
    from sqlalchemy import text

    for k in sorted(set(keys)):
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": "ch2:c2:" + k})


def _c2_assign(conn, df: pd.DataFrame, asset_type: str, units: C2Units, c01: dict) -> pd.DataFrame:
    hit = df["building_key"].astype(str).isin(units)
    sub = df.loc[hit]
    groups: dict[str, set[str]] = {}
    for k, rb in zip(sub["building_key"].astype(str), building_key_raw_series(sub, asset_type)):
        if k in groups:
            continue
        raw = _key_raw_for(rb, k, c01)
        groups[k] = c2_derived_keys(raw, units[k]) if raw is not None else set()
    counts = existing_main_lot_counts(conn, groups)
    return apply_building_key_split_c2(df, asset_type, units=units, c01_units=c01, existing_counts=counts)


def apply_c2_split_from_db(engine, df: pd.DataFrame, asset_type: str) -> pd.DataFrame:
    """월간 적재용: 집합 DB 의 C-2 판정 표를 읽어 키를 배정하고, 새 조각은 표에 자동 등록한다.

    - 표가 없거나 비었거나 비상 해제면 그대로 돌려준다. 판정 키가 배치에 없으면 원장을 조회하지 않는다.
    - 배치에 든 판정 키마다 advisory lock 을 잡은 뒤 판정 표를 **다시 읽고** 배정한다(동시 실행 안전).
    - 등록이 DO NOTHING 으로 충돌하면(잠금 밖 다른 쓰기) 표의 실제 조각 번호를 다시 읽어 그 값으로 다시 배정한다."""
    if df.empty or engine is None or "building_key" not in df.columns or asset_type == _PRESALE_KEY_ASSET:
        return df
    with engine.begin() as conn:
        pre = load_split_units_c2(conn)
        if not pre:
            return df
        keys = sorted(set(df["building_key"].astype(str)) & set(pre))
        if not keys:
            return df
        _lock_c2_keys(conn, keys)
        units = load_split_units_c2(conn)               # 잠금 뒤 다시 읽기 — 다른 실행이 방금 등록한 조각 반영
        if not units or not (set(keys) & set(units)):
            return df
        c01 = load_split_units()
        out = _c2_assign(conn, df, asset_type, units, c01)
        res = register_c2_parts(conn, out.attrs.get("c2_new_parts") or [])
        conflict = [r for r in res if not r["registered"]]
        if conflict:
            log.warning("c2 split: 자동 등록 충돌 %d건 — 판정 표의 실제 값으로 다시 배정", len(conflict))
            units = load_split_units_c2(conn)
            out = _c2_assign(conn, df, asset_type, units, c01)
            res2 = register_c2_parts(conn, out.attrs.get("c2_new_parts") or [])
            if any(not r["registered"] for r in res2):
                raise RuntimeError("c2 split: 다시 배정한 뒤에도 자동 등록이 충돌함 — 적재 중단(판정 표 확인)")
            res = [r for r in res if r["registered"]] + res2
        n = sum(1 for r in res if r["registered"])
        if n:
            log.warning("c2 split: 새 조각 %d개를 판정 표에 자동 등록(source=%s) — 판정 검토 대상", n, C2_AUTO_SOURCE)
        out.attrs["c2_registered"] = res
    return out


RENT_C2_AUTO_SOURCE = "auto_ingest"


def _rent_piece(base: str, part: int, raw: str | None) -> str:
    if part == 0 or not raw:
        return base
    return c2_key(raw, f"p{int(part)}")


def apply_rent_c2_assignment(
    df: pd.DataFrame,
    asset_type: str,
    *,
    units: dict | None = None,
    collective_unique: dict | None = None,
    raw_of: dict | None = None,
) -> pd.DataFrame:
    """임대 판정 표에 있는 본번만 기존 part로 보낸다.

    units 가 없거나 비면 표를 만들지 않은 것과 같이 키를 그대로 둔다.
    표에 없는 본번은 collective_unique 에 조각이 하나일 때만 그 part 를 쓰고,
    아니면 part 0 과 pending 한 행이다. 새 part 번호는 만들지 않는다.
    """
    out = df.copy()
    out.attrs["rent_c2_pending"] = []
    out.attrs["rent_c2_new_parts"] = []
    if not units or out.empty or "building_key" not in out.columns or asset_type in ("detached", _PRESALE_KEY_ASSET):
        return out
    codes = out["beopjungri_code"].astype(str).str.strip().str[:10] if "beopjungri_code" in out.columns else pd.Series("", index=out.index)
    lots = (out["lot_number"] if "lot_number" in out.columns else pd.Series("", index=out.index)).map(main_lot_of)
    if raw_of is None:
        raw_series = building_key_raw_series(out, asset_type)
        c01 = load_split_units()
        recovered = []
        for key, raw in zip(out["building_key"], raw_series):
            recovered.append(_key_raw_for(str(raw), str(key), c01))
    else:
        recovered = [raw_of.get(str(key)) for key in out["building_key"]]
    new_keys: list[str] = []
    pending: list[dict] = []
    seen: set[tuple] = set()
    for key, code, lot, raw in zip(out["building_key"], codes, lots, recovered):
        base = str(key)
        slot = (base, str(code), lot or "")
        hit = units.get(slot)
        if hit is not None:
            part = int(hit[0])
            new_keys.append(_rent_piece(base, part, raw))
            continue
        uniq = None if not collective_unique else collective_unique.get(slot)
        if isinstance(uniq, int):
            new_keys.append(_rent_piece(base, int(uniq), raw))
            continue
        new_keys.append(base)
        if slot not in seen:
            seen.add(slot)
            pending.append({
                "base_key": base,
                "asset_type": asset_type,
                "beopjungri_code": str(code),
                "main_lot": lot or "",
                "part": 0,
                "decision": "pending",
                "evidence": "",
                "source": RENT_C2_AUTO_SOURCE,
            })
    out["building_key"] = new_keys
    out.attrs["rent_c2_pending"] = pending
    out.attrs["rent_c2_new_parts"] = []
    return out
