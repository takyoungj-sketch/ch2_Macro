# -*- coding: utf-8 -*-
"""복합 실거래 마스킹 지번 복원 — 실측 재현 + 검증축 판별력 측정.

D-046 규칙을 코드로 고정한다. `docs/BUILT_DATA_ENRICHMENT.md` §3·§12 재현 절차.

  후보  = 법정동 + 마스킹 자릿수 범위 안의 대장 필지
  A1    = 연면적 완전일치(±0.011㎡) 후보가 1개
  A2    = 완전일치가 다수 → 대지면적으로 1개 (표제부 → 총괄표제부 → 토지대장 순)
  미상  = 그 외. 다수결·최근접으로 메우지 않는다 (D-046)

같이 재는 것 — 왜 이 스크립트가 단순 재현이 아닌가

  1. 정밀도: 필터에 쓰지 않은 도로명·사용승인연도, 그리고 상가·공장은 원천 용도지역
  2. **검증축 판별력**: 경합 후보끼리 도로명·용도지역이 몇 % 같은가.
     같을수록 "도로명 98.9%"가 매칭 정확도의 증거가 되지 못한다. 이걸 재지 않으면
     정밀도 숫자를 해석할 수 없다.
  3. **A2 판정 출처**: 대지면적을 표제부·총괄표제부·토지대장 중 무엇이 갈랐는지.
     "충북이 청주보다 오른 건 토지대장 덕"이라는 미검증 귀속을 가른다.
  4. **시점 정합**: 기본 `--snapshot all` + `time_fallback`.
     거래월에 가장 가까운 과거 표제부로 A1/A2. 실패 시에만 다른 본. 합집합은 대조군.

캐시
  표제부 전국 스캔(3.6GB·806만 행)은 시도 필터 결과를 `_cache/` 에 CSV로 남긴다.
  두 번째 실행부터 초 단위. `--refresh` 로 강제 재생성.

사용
  python -m built.recover_address --sido 43                 # 기본: 세 본 + time_fallback
  python -m built.recover_address --sido 43 --snapshot 2026-07  # 최신본만 (구 경로)
  python -m built.recover_address --sido 43 --no-zone       # AL_D155 건너뜀
  python -m built.recover_address --sido 43 --apply-enrichment  # 확정 행 DB 적재 (기존 해시 동결)
  python -m built.recover_address --sido all --apply-enrichment  # 원장 전 시도. 이미 적재된 시도는 건너뜀
  python -m built.recover_address --sido 43 --min-year 2019     # 제품 게이트 (기본값). 2018 이전은 매칭하지 않음
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from built.db_utils import get_built_engine  # noqa: E402
from built.enrichment_rows import apply_enrichment_rows, to_enrichment_records  # noqa: E402
from built.snapshot_policy import apply_snapshot_policy, policy_coverage  # noqa: E402

RAW = REPO / "raw" / "raw addition"
BLDRGST_DIR = RAW / "건축물대장(건축허브)"
LAND_LEDGER_DIR = RAW / "토지대장csv(브이월드)"
ZONE_DIR = RAW / "토지이용계획csv(브이월드)"
CACHE = Path(__file__).parent / "_cache"

# 표제부·총괄표제부 스냅샷 (건축HUB 누적분). 전국.
SNAPSHOTS = {"2024-09": "2024년+09월", "2025-07": "2025년+07월", "2026-07": "2026년+07월"}
PRIMARY = "2026-07"

# 0-based 열 위치 — `_tmp_bldreg_extract_cheongju.py` 실측 확인분
TITLE_COLS = {
    "pk": 0,
    "addr_lot": 5,
    "addr_road": 6,
    "sigungu_code": 8,
    "bjd_code": 9,
    "bun": 11,
    "ji": 12,
    "land_area": 25,
    "gross_area": 28,
    "struct_name": 32,
    "use_name": 35,
    "floors_above": 43,
    "approve_date": 60,
}
SUMMARY_COLS = {
    "sigungu_code": 10,
    "bjd_code": 11,
    "bun": 13,
    "ji": 14,
    "land_area": 24,
}

# 용도지역만 남긴다. UQQ(지구단위)·UQS(도로)·UQM(취락) 등 용도지구·시설은 제외.
# 개발제한구역(UDV)도 밖.
ZONE_CODE_RE = re.compile(r"^UQ[ABCD]", re.IGNORECASE)

# 국토계획법 4대 구분 중 '도시지역'·'관리지역'은 세부 용도지역이 반드시 따라오는 상위 라벨이다.
# 세부가 함께 있으면 버린다. 코드(UQA001)로 판정하면 시도마다 코드가 달라 새는데,
# 실제로 서울은 32.5% 필지에서 세부가 있는데도 '도시지역'이 대표값으로 뽑혔다.
# '농림지역'·'자연환경보전지역'은 세부가 없는 최종 용도지역이라 제외 대상이 아니다.
ZONE_COARSE_LABELS = {"도시지역", "도시지역기타", "비도시지역", "관리지역", "도시관리계획 입안중"}
ZONE_COARSE = {"UQA001"}
ZONE_SUFFIX_RE = re.compile(r"(지역|지구|구역)$")
ROAD_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]*(?:대로|로|길)[0-9]*(?:번길)?")

GROSS_TOL = 0.011  # ±0.01㎡ 완전일치 (부동소수 여유 포함)


# --------------------------------------------------------------------------- #
# 정규화
# --------------------------------------------------------------------------- #
def nz(v: Any) -> str:
    """pandas NA/None/NaN → ''. str(nan) 이 'nan' 으로 새는 것을 막는다."""
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA:
        return ""
    return str(v)


def to_f(v: Any) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return math.nan
    return f if f > 0 else math.nan


def to_i(v: Any) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def mask_range(lot: Any) -> tuple[int, int] | None:
    """'7**' → (700, 799). 산 지번과 부번 표기가 있는 건 대상 아님."""
    s = str(lot or "").strip()
    if not s or s.startswith("산") or not re.fullmatch(r"\d*\*+", s):
        return None
    stars = s.count("*")
    exposed = s[: len(s) - stars]
    span = 10**stars
    if not exposed:
        return 1, span - 1
    base = int(exposed) * span
    return base, base + span - 1


def lot_str(bun: int, ji: int) -> str:
    return f"{bun}-{ji}" if ji else f"{bun}"


def road_token(s: Any) -> str:
    """대장 도로명대지위치에서 도로명 토큰만. '…서원구 수곡로106번길 12' → '수곡로106번길'."""
    t = re.sub(r"\s+", " ", nz(s)).strip()
    if not t:
        return ""
    found = ROAD_TOKEN_RE.findall(t)
    return max(found, key=len) if found else ""


ZONE_FAMILIES = ("주거", "상업", "공업", "녹지", "관리", "농림", "자연환경")


def zfamily(label: Any) -> str:
    """'제2종일반주거' → '주거', '계획관리' → '관리'. 계열이 같으면 세부 등급 차이일 뿐이다."""
    t = zkey(label)
    for fam in ZONE_FAMILIES:
        if fam in t:
            return fam
    return ""


def zlabels(zone: dict[str, list[str]], key: Any) -> list[str]:
    """그 필지의 용도지역 전부. 세부 라벨이 있으면 상위 라벨('도시지역' 등)은 버린다.

    캐시에는 원본 라벨을 그대로 두고 여기서 걸러낸다. 캐시를 다시 만들면 1.8GB를 재스캔해야 한다.
    """
    labels = zone.get(key or "", [])
    fine = [x for x in labels if x not in ZONE_COARSE_LABELS]
    return fine or labels


def zone_primary(zone: dict[str, list[str]], key: Any) -> str:
    """대표 용도지역 = zlabels 의 첫 항. 순서는 order_zone_labels (빈도, 동수는 라벨 문자열)."""
    labels = zlabels(zone, key)
    return labels[0] if labels else ""


def order_zone_labels(cnt: Counter, broad: set[str]) -> list[str]:
    """빈도 내림차순. 동수는 라벨 문자열 오름차순. 대분류는 뒤로.

    Counter.most_common() 은 동수일 때 삽입 순이라 재스캔마다 대표가 바뀔 수 있다.
    """
    ordered = [lab for lab, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))]
    return [x for x in ordered if x not in broad] + [x for x in ordered if x in broad]


def zkey(s: Any) -> str:
    """'제1종일반주거지역' → '제1종일반주거'. 원장 라벨은 접미어가 없다."""
    t = re.sub(r"\s+", "", nz(s))
    while ZONE_SUFFIX_RE.search(t):
        t = ZONE_SUFFIX_RE.sub("", t)
    return t


# --------------------------------------------------------------------------- #
# 1. 건축물대장 추출 (캐시)
# --------------------------------------------------------------------------- #
def _scan_pipe_file(src: Path, cols: dict[str, int], out: Path, sido: str) -> dict:
    kept = total = bad = 0
    need = max(cols.values())
    with src.open(encoding="utf-8-sig", errors="replace") as f, out.open(
        "w", encoding="utf-8", newline=""
    ) as w:
        writer = csv.writer(w)
        writer.writerow(list(cols))
        sg = cols["sigungu_code"]
        for line in f:
            total += 1
            parts = line.rstrip("\n").split("|")
            if len(parts) <= need:
                bad += 1
                continue
            if not parts[sg].startswith(sido):
                continue
            writer.writerow([parts[i] for i in cols.values()])
            kept += 1
    return {"src": src.name, "rows_read": total, "rows_kept": kept, "rows_short": bad}


def _scan_pipe_file_multi(
    src: Path,
    cols: dict[str, int],
    out_by_sido: dict[str, Path],
) -> dict[str, Any]:
    """전국 원본 1회 스캔 → 시도별 CSV. 시도마다 3.5GB를 다시 읽지 않는다."""
    need = max(cols.values())
    sg = cols["sigungu_code"]
    files: dict[str, Any] = {}
    writers: dict[str, Any] = {}
    kept = {s: 0 for s in out_by_sido}
    total = bad = 0
    try:
        for sido, path in out_by_sido.items():
            path.parent.mkdir(exist_ok=True)
            f = path.open("w", encoding="utf-8", newline="")
            files[sido] = f
            w = csv.writer(f)
            w.writerow(list(cols))
            writers[sido] = w
        with src.open(encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                total += 1
                parts = line.rstrip("\n").split("|")
                if len(parts) <= need:
                    bad += 1
                    continue
                w = writers.get(parts[sg][:2])
                if w is None:
                    continue
                w.writerow([parts[i] for i in cols.values()])
                kept[parts[sg][:2]] += 1
    finally:
        for f in files.values():
            f.close()
    return {"src": src.name, "rows_read": total, "rows_short": bad, "rows_kept": kept}


def warm_register_caches(sidos: list[str], snapshots: list[str], refresh: bool = False) -> None:
    CACHE.mkdir(exist_ok=True)
    for snap in snapshots:
        tag = SNAPSHOTS[snap]
        need_title = [
            s for s in sidos if refresh or not (CACHE / f"title_{s}_{snap}.csv").exists()
        ]
        if need_title:
            src = BLDRGST_DIR / f"국토교통부_건축물대장_표제부+({tag})" / "mart_djy_03.txt"
            print(f"[표제부 일괄] {snap} → {need_title}", flush=True)
            meta = _scan_pipe_file_multi(
                src, TITLE_COLS, {s: CACHE / f"title_{s}_{snap}.csv" for s in need_title}
            )
            print(f"[표제부 일괄] {snap} read={meta['rows_read']:,}", flush=True)
        need_summ = [
            s for s in sidos if refresh or not (CACHE / f"summary_{s}_{snap}.csv").exists()
        ]
        if need_summ:
            src = BLDRGST_DIR / f"국토교통부_건축물대장_총괄표제부+({tag})" / "mart_djy_02.txt"
            print(f"[총괄 일괄] {snap} → {need_summ}", flush=True)
            meta = _scan_pipe_file_multi(
                src, SUMMARY_COLS, {s: CACHE / f"summary_{s}_{snap}.csv" for s in need_summ}
            )
            print(f"[총괄 일괄] {snap} read={meta['rows_read']:,}", flush=True)


def ledger_sidos(eng) -> list[str]:
    sql = text(
        """
        SELECT sido_code
        FROM built_transactions
        WHERE is_valid AND gross_area > 0 AND is_partial_ownership IS NOT TRUE
          AND sido_code IS NOT NULL AND btrim(sido_code) <> ''
        GROUP BY 1
        ORDER BY 1
        """
    )
    with eng.connect() as conn:
        return [str(r[0]).strip() for r in conn.execute(sql)]


def sidos_with_enrichment(eng) -> set[str]:
    sql = text(
        """
        SELECT DISTINCT t.sido_code
        FROM built_transaction_enrichment e
        JOIN built_transactions t ON t.transaction_hash = e.transaction_hash
        WHERE t.sido_code IS NOT NULL
        """
    )
    with eng.connect() as conn:
        return {str(r[0]).strip() for r in conn.execute(sql)}


def load_register(sido: str, snapshot: str, refresh: bool) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """표제부·총괄표제부의 시도 필터 결과. 캐시가 있으면 재사용."""
    tag = SNAPSHOTS[snapshot]
    CACHE.mkdir(exist_ok=True)
    title_cache = CACHE / f"title_{sido}_{snapshot}.csv"
    summ_cache = CACHE / f"summary_{sido}_{snapshot}.csv"
    meta: dict = {"snapshot": snapshot}

    if refresh or not title_cache.exists():
        src = BLDRGST_DIR / f"국토교통부_건축물대장_표제부+({tag})" / "mart_djy_03.txt"
        print(f"[표제부] 전국 스캔 시작 — {src.name} ({src.stat().st_size / 2**30:.1f}GB)", flush=True)
        meta["title"] = _scan_pipe_file(src, TITLE_COLS, title_cache, sido)
        print(f"[표제부] {meta['title']}", flush=True)
    if refresh or not summ_cache.exists():
        src = BLDRGST_DIR / f"국토교통부_건축물대장_총괄표제부+({tag})" / "mart_djy_02.txt"
        print(f"[총괄표제부] 스캔 시작 — {src.name}", flush=True)
        meta["summary"] = _scan_pipe_file(src, SUMMARY_COLS, summ_cache, sido)
        print(f"[총괄표제부] {meta['summary']}", flush=True)

    title = pd.read_csv(title_cache, dtype=str, keep_default_na=False)
    summ = pd.read_csv(summ_cache, dtype=str, keep_default_na=False)
    meta["title_rows"] = len(title)
    meta["summary_rows"] = len(summ)
    return title, summ, meta


def load_land_ledger(sido: str, refresh: bool) -> dict[tuple[str, str], float]:
    """토지대장 지목 대(垈) 필지의 면적. (법정동코드, 지번) → 면적."""
    CACHE.mkdir(exist_ok=True)
    cache = CACHE / f"land_ledger_{sido}.json"
    if cache.exists() and not refresh:
        raw = json.loads(cache.read_text(encoding="utf-8"))
        return {tuple(k.split("|", 1)): v for k, v in raw.items()}  # type: ignore[misc]

    srcs = sorted(LAND_LEDGER_DIR.glob(f"AL_D003_{sido}_*/*.csv"))
    if not srcs:
        print(f"[토지대장] {sido} 파일 없음 — 대지면적 대체값 없이 진행", flush=True)
        return {}
    src = srcs[-1]
    print(f"[토지대장] {src.name} 읽는 중", flush=True)
    out: dict[tuple[str, str], float] = {}
    for enc in ("cp949", "utf-8-sig", "euc-kr"):
        try:
            reader = pd.read_csv(
                src,
                usecols=["법정동코드", "지번", "지목코드", "면적"],
                dtype=str,
                chunksize=400_000,
                encoding=enc,
            )
            for chunk in reader:
                sub = chunk[chunk["지목코드"].astype(str).str.zfill(2) == "08"]
                if sub.empty:
                    continue
                for b, lot, area in zip(sub["법정동코드"], sub["지번"], sub["면적"]):
                    a = to_f(area)
                    if math.isnan(a):
                        continue
                    out.setdefault((str(b).zfill(10), str(lot).strip()), a)
            break
        except UnicodeDecodeError:
            continue
    cache.write_text(
        json.dumps({f"{k[0]}|{k[1]}": v for k, v in out.items()}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[토지대장] 대(垈) 필지 {len(out):,}건", flush=True)
    return out


# --------------------------------------------------------------------------- #
# 2. 필지 인덱스
# --------------------------------------------------------------------------- #
def build_parcels(
    title: pd.DataFrame, summ: pd.DataFrame, land_ledger: dict[tuple[str, str], float]
) -> tuple[dict, dict]:
    """(법정동10, 본번, 부번) → {land, land_src, buildings[]}"""
    summ_land: dict[tuple, float] = {}
    for r in summ.itertuples(index=False):
        bun = to_i(r.bun)
        if bun is None:
            continue
        a = to_f(r.land_area)
        if math.isnan(a):
            continue
        key = (str(r.sigungu_code).strip() + str(r.bjd_code).strip(), bun, to_i(r.ji) or 0)
        summ_land.setdefault(key, a)

    parcels: dict[tuple, dict] = {}
    for r in title.itertuples(index=False):
        bun = to_i(r.bun)
        if bun is None:
            continue
        bjd10 = str(r.sigungu_code).strip() + str(r.bjd_code).strip()
        key = (bjd10, bun, to_i(r.ji) or 0)
        p = parcels.setdefault(key, {"land": math.nan, "land_src": None, "b": []})
        p["b"].append(
            {
                "gross": to_f(r.gross_area),
                "struct": str(r.struct_name).strip(),
                "floors": to_i(r.floors_above),
                "approve": to_i(str(r.approve_date)[:4]),
                "use": str(r.use_name).strip(),
                "road": road_token(r.addr_road),
                "addr": re.sub(r"\s+", " ", nz(r.addr_lot)).strip(),
                "addr_road_full": re.sub(r"\s+", " ", nz(r.addr_road)).strip(),
            }
        )
        if p["land_src"] is None:
            a = to_f(r.land_area)
            if not math.isnan(a):
                p["land"], p["land_src"] = a, "title"
            else:
                a = summ_land.get(key, math.nan)
                if not math.isnan(a):
                    p["land"], p["land_src"] = a, "summary"
                else:
                    a = land_ledger.get((bjd10, lot_str(key[1], key[2])), math.nan)
                    if not math.isnan(a):
                        p["land"], p["land_src"] = a, "land_ledger"

    idx: dict[str, list[tuple]] = defaultdict(list)
    for key in parcels:
        idx[key[0]].append(key)
    return parcels, idx


# --------------------------------------------------------------------------- #
# 3. 매칭
# --------------------------------------------------------------------------- #
def match_all(tx: pd.DataFrame, parcels: dict, idx: dict) -> pd.DataFrame:
    rows: list[dict] = []
    for r in tx.itertuples(index=False):
        rec: dict[str, Any] = {
            "id": int(r.id),
            "transaction_hash": (str(getattr(r, "transaction_hash", "") or "").strip() or None),
            "asset_type": r.asset_type,
            "contract_year": to_i(r.contract_year),
            "contract_month": to_i(getattr(r, "contract_month", None)),
            "tx_road": re.sub(r"\s+", "", nz(r.road_name)),
            "tx_zone": zkey(r.zone_type),
            "tx_age": to_f(r.building_age),
            "tier": None,
            "fail": None,
            "parcel": None,
            "n_range": 0,
            "n_exact": 0,
            "land_src": None,
            "struct": None,
            "floors": None,
            "approve": None,
            "reg_road": None,
            "reg_addr": None,
            "reg_addr_road": None,
            "reg_use": None,
            "gross_area": to_f(r.gross_area),
            "land_area": to_f(r.land_area),
            "tx_lot": nz(r.lot_number),
            # 판별력용 — 경합/범위 후보가 검증축에서 나와 같은 값을 갖는 비율
            "rival_lots": None,
            "road_share_range": math.nan,
            "road_share_rival": math.nan,
            "approve_share_rival": math.nan,
            "struct_share_rival": math.nan,
        }
        bjd = nz(r.beopjungri_code).strip()
        rng = mask_range(r.lot_number)
        g = to_f(r.gross_area)
        la = to_f(r.land_area)

        if not bjd:
            rec["fail"] = "no_bjd_code"
        elif rng is None:
            rec["fail"] = "lot_not_parsable"
        elif math.isnan(g):
            rec["fail"] = "no_gross_area"
        else:
            lo, hi = rng
            keys = [k for k in idx.get(bjd, ()) if lo <= k[1] <= hi]
            rec["n_range"] = len(keys)
            if not keys:
                rec["fail"] = "no_parcel_in_range"
            else:
                exact = [
                    k
                    for k in keys
                    if any(
                        not math.isnan(b["gross"]) and abs(b["gross"] - g) <= GROSS_TOL
                        for b in parcels[k]["b"]
                    )
                ]
                rec["n_exact"] = len(exact)
                chosen = None
                if len(exact) == 1:
                    chosen, rec["tier"] = exact[0], "A1"
                elif not exact:
                    rec["fail"] = "no_gross_match"
                else:
                    narrowed = [
                        k
                        for k in exact
                        if not math.isnan(parcels[k]["land"])
                        and not math.isnan(la)
                        and abs(parcels[k]["land"] - la) <= max(0.5, la * 0.01)
                    ]
                    if len(narrowed) == 1:
                        chosen, rec["tier"] = narrowed[0], "A2"
                        rec["land_src"] = parcels[chosen]["land_src"]
                    else:
                        rec["fail"] = "exact_multi"

                # 판별력 — 경합 후보가 있었던 건에서만 의미가 있다
                pick = chosen or (exact[0] if exact else None)
                if pick is not None:
                    mine = _pick_building(parcels[pick], g)
                    if mine["road"]:
                        rec["road_share_range"] = _share(parcels, keys, pick, g, "road", mine)
                        if len(exact) >= 2:
                            rec["road_share_rival"] = _share(parcels, exact, pick, g, "road", mine)
                    if len(exact) >= 2:
                        rec["approve_share_rival"] = _share(parcels, exact, pick, g, "approve", mine)
                        rec["struct_share_rival"] = _share(parcels, exact, pick, g, "struct", mine)
                        rec["rival_lots"] = [
                            f"{k[0]}|{lot_str(k[1], k[2])}" for k in exact if k != pick
                        ]

                if chosen is not None:
                    b = min(
                        (x for x in parcels[chosen]["b"] if not math.isnan(x["gross"])),
                        key=lambda x: abs(x["gross"] - g),
                    )
                    rec["parcel"] = f"{chosen[0]}|{lot_str(chosen[1], chosen[2])}"
                    rec["struct"] = b["struct"] or None
                    rec["floors"] = b["floors"]
                    rec["approve"] = b["approve"]
                    rec["reg_road"] = b["road"]
                    rec["reg_addr"] = b["addr"] or None
                    rec["reg_addr_road"] = b["addr_road_full"] or None
                    rec["reg_use"] = b["use"] or None
        rows.append(rec)
    return pd.DataFrame(rows)


def _pick_building(p: dict, g: float) -> dict:
    """연면적이 맞는 동. 없으면 그 필지의 첫 동."""
    cands = [b for b in p["b"] if not math.isnan(b["gross"]) and abs(b["gross"] - g) <= GROSS_TOL]
    pool = cands or p["b"]
    for b in pool:
        if b["road"]:
            return b
    return pool[0] if pool else {"road": "", "struct": "", "approve": None}


def _share(parcels: dict, keys: list, pick: tuple, g: float, attr: str, mine: dict) -> float:
    """경합 후보 중 `attr` 값이 채택 후보와 같은 비율. 사용승인연도는 ±1년."""
    others = [k for k in keys if k != pick]
    if not others:
        return math.nan
    mine_v = mine.get(attr)
    if attr == "road" and not mine_v:
        return math.nan
    if attr in ("struct", "approve") and mine_v in (None, ""):
        return math.nan
    same = compared = 0
    for k in others:
        vals = {b[attr] for b in parcels[k]["b"] if b[attr] not in (None, "")}
        if not vals:
            continue
        compared += 1
        if attr == "approve":
            if any(abs(int(v) - int(mine_v)) <= 1 for v in vals):
                same += 1
        elif mine_v in vals:
            same += 1
    return same / compared if compared else math.nan


# --------------------------------------------------------------------------- #
# 4. 용도지역 (AL_D155)
# --------------------------------------------------------------------------- #
def load_zone(sido: str, keep: set[str], refresh: bool) -> dict[str, list[str]]:
    """확정 필지 + 경합 후보 필지의 용도지역 **전부**. keep 은 '법정동10|지번' 문자열.

    하나만 남기면 불일치를 분해할 수 없다. 한 필지가 두 용도지역에 걸치는 경우가 있어서
    원장 라벨이 '첫 번째'가 아니라 '두 번째' 라벨과 맞는 일이 생긴다.
    반환 리스트는 빈도 내림차순(동수는 라벨 문자열), UQA001('도시지역') 같은 상위 라벨은 맨 뒤.
    """
    CACHE.mkdir(exist_ok=True)
    cache = CACHE / f"zone_all_{sido}_v2.json"
    if cache.exists() and not refresh:
        cur: dict[str, list[str]] = json.loads(cache.read_text(encoding="utf-8"))
        if keep <= set(cur):
            print(f"[AL_D155] 캐시 재사용 {len(cur):,}필지", flush=True)
            return cur
        print(f"[AL_D155] 캐시에 없는 필지 {len(keep - set(cur)):,}건 - 재적재", flush=True)

    srcs = sorted(ZONE_DIR.glob(f"AL_D155_{sido}_*/*.csv"))
    srcs = [p for p in srcs if "head" not in p.name.lower()]
    if not srcs:
        print(f"[AL_D155] {sido} 파일 없음 — 용도지역 없이 진행", flush=True)
        return {}
    src = srcs[-1]
    print(f"[AL_D155] {src.name} ({src.stat().st_size / 2**30:.1f}GB) 읽는 중", flush=True)

    tally: dict[str, Counter] = defaultdict(Counter)
    coarse: dict[str, set[str]] = defaultdict(set)
    for enc in ("cp949", "utf-8-sig", "euc-kr"):
        try:
            reader = pd.read_csv(
                src,
                usecols=lambda c: c in ("법정동코드", "지번", "용도지역지구코드", "용도지역지구명"),
                dtype=str,
                chunksize=300_000,
                encoding=enc,
            )
            for chunk in reader:
                code = chunk["용도지역지구코드"].astype(str).str.upper()
                sub = chunk[code.str.match(ZONE_CODE_RE, na=False)]
                if sub.empty:
                    continue
                k = sub["법정동코드"].astype(str).str.zfill(10) + "|" + sub["지번"].astype(str).str.strip()
                sel = k.isin(keep)
                if not sel.any():
                    continue
                for key, c, name in zip(
                    k[sel], sub["용도지역지구코드"][sel], sub["용도지역지구명"][sel]
                ):
                    label = str(name).strip()
                    if not label:
                        continue
                    tally[key][label] += 1
                    if str(c).upper() in ZONE_COARSE:
                        coarse[key].add(label)
            break
        except UnicodeDecodeError:
            continue

    out: dict[str, list[str]] = {}
    for key, cnt in tally.items():
        broad = coarse.get(key, set())
        ordered = order_zone_labels(cnt, broad)
        out[key] = [x for x in ordered if x not in broad] + [x for x in ordered if x in broad]
    found = len(out)
    # AL_D155 에 없는 필지도 빈 리스트로 캐시한다. 안 하면 매 실행마다 2.5GB를 다시 읽는다.
    for k in keep - set(out):
        out[k] = []
    cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"[AL_D155] 용도지역 확보 {found:,}필지 / 요청 {len(keep):,}", flush=True)
    return out


# --------------------------------------------------------------------------- #
# 5. 리포트
# --------------------------------------------------------------------------- #
def _pct(a: int, b: int) -> float:
    return round(100 * a / b, 1) if b else 0.0


def _mean_pct(s: pd.Series) -> float | None:
    v = s.dropna()
    return round(float(v.mean()) * 100, 1) if len(v) else None


def _expected_struct(implied: dict, confound: dict) -> float | None:
    """구조 값이 맞을 기대 확률. 매칭 정확도는 건물 고유 축(사용승인연도)으로 추정한다."""
    p = implied.get("approve_year")
    c = confound.get("structure")
    if p is None or c is None:
        return None
    p, c = p / 100, c / 100
    return round((p + (1 - p) * c) * 100, 1)


def report(res: pd.DataFrame, zone: dict[str, list[str]], meta: dict) -> dict:
    res = res.copy()
    res["zone_recovered"] = [zone_primary(zone, p) if p else "" for p in res["parcel"]]
    ok = res["tier"].notna()

    out: dict[str, Any] = {"meta": meta, "n_total": int(len(res)), "by_asset": {}}
    pooled: dict[str, list[int]] = {"road": [0, 0], "approve_year": [0, 0], "zone_vs_source": [0, 0]}

    for at, sub in res.groupby("asset_type"):
        m = sub["tier"].notna()
        conf = sub[m]
        road_cmp = conf[(conf["tx_road"] != "") & conf["reg_road"].notna() & (conf["reg_road"] != "")]
        # 원장은 도로명만('수곡로106번길'), 대장은 토큰만 남겼으니 양방향 포함으로 본다
        road_hit = sum(
            1
            for r in road_cmp.itertuples(index=False)
            if r.tx_road in r.reg_road or r.reg_road in r.tx_road
        )
        year_cmp = conf[conf["approve"].notna() & conf["tx_age"].notna() & conf["contract_year"].notna()]
        year_hit = sum(
            1
            for r in year_cmp.itertuples(index=False)
            if abs((r.contract_year - r.tx_age) - r.approve) <= 1
        )
        zc = conf[(conf["tx_zone"] != "") & (conf["zone_recovered"] != "")]
        zone_hit = sum(1 for r in zc.itertuples(index=False) if zkey(r.zone_recovered) == r.tx_zone)

        pooled["road"][0] += road_hit
        pooled["road"][1] += len(road_cmp)
        pooled["approve_year"][0] += year_hit
        pooled["approve_year"][1] += len(year_cmp)
        pooled["zone_vs_source"][0] += zone_hit
        pooled["zone_vs_source"][1] += len(zc)

        out["by_asset"][at] = {
            "n": int(len(sub)),
            "confirmed": int(m.sum()),
            "confirmed_pct": _pct(int(m.sum()), len(sub)),
            "tier": {k: int(v) for k, v in sub["tier"].value_counts().items()},
            "struct_filled_pct": _pct(int(conf["struct"].notna().sum()), len(sub)),
            "zone_recovered_pct": _pct(int((conf["zone_recovered"] != "").sum()), len(sub)),
            "zone_source_pct": _pct(int((sub["tx_zone"] != "").sum()), len(sub)),
            "precision": {
                "road": {"n": int(len(road_cmp)), "pct": _pct(road_hit, len(road_cmp))},
                "approve_year_pm1": {"n": int(len(year_cmp)), "pct": _pct(year_hit, len(year_cmp))},
                "zone_vs_source": {"n": int(len(zc)), "pct": _pct(zone_hit, len(zc))},
            },
            "fail": {k: int(v) for k, v in sub["fail"].value_counts().items()},
            "fail_pct": {k: _pct(int(v), len(sub)) for k, v in sub["fail"].value_counts().items()},
            "struct_top": {k: int(v) for k, v in conf["struct"].value_counts().head(8).items()},
        }

    # ---- 검증축 판별력 ----
    amb = res[res["n_exact"] >= 2]
    zone_rival_same = []
    for r in amb.itertuples(index=False):
        mine = zkey(zone_primary(zone, r.parcel)) if r.parcel else ""
        if not mine or not r.rival_lots:
            continue
        rv = [zkey(zone_primary(zone, x)) for x in r.rival_lots]
        rv = [x for x in rv if x]
        if rv:
            zone_rival_same.append(sum(1 for x in rv if x == mine) / len(rv))

    confound = {
        "road": _mean_pct(amb["road_share_rival"]),
        "approve_year": _mean_pct(amb["approve_share_rival"]),
        "structure": _mean_pct(amb["struct_share_rival"]),
        "zone": (
            round(100 * sum(zone_rival_same) / len(zone_rival_same), 1) if zone_rival_same else None
        ),
    }
    # 관측 일치율 = p·1 + (1−p)·c  →  p = (관측 − c) / (1 − c)
    obs = {
        "road": _pct(*pooled["road"]) if pooled["road"][1] else None,
        "approve_year": _pct(*pooled["approve_year"]) if pooled["approve_year"][1] else None,
        "zone": _pct(*pooled["zone_vs_source"]) if pooled["zone_vs_source"][1] else None,
    }
    implied = {}
    for axis, c in confound.items():
        o = obs.get(axis)
        if o is None or c is None or c >= 99.9:
            implied[axis] = None
            continue
        implied[axis] = round(max(0.0, min(100.0, (o - c) / (100 - c) * 100)), 1)

    out["discriminating_power"] = {
        "note": "confound_pct = 경합 후보(연면적이 똑같은 다른 필지)가 그 축에서 나와 같은 값을 갖는 비율. "
        "높으면 '틀린 후보를 골랐어도 통과'하므로 관측 일치율이 매칭 정확도의 증거가 되지 못한다. "
        "implied_match_accuracy_pct = 관측 일치율을 confound 로 보정한 값.",
        "n_ambiguous_tx": int(len(amb)),
        "n_zone_rival_pairs": len(zone_rival_same),
        "confound_pct": confound,
        "observed_agreement_pct": obs,
        "implied_match_accuracy_pct": implied,
        "road_same_among_range_pct": _mean_pct(res["road_share_range"]),
        # 구조는 대조할 원천이 없다. 대신 기대 정확도를 낸다:
        #   p(매칭 정확) + (1−p)·(틀려도 구조가 같을 확률)
        "expected_structure_accuracy_pct": _expected_struct(implied, confound),
    }

    # ---- 용도지역 불일치 3분해 (상가·공장만 원천 라벨이 있다) ----
    zc_all = res[ok & (res["tx_zone"] != "") & (res["zone_recovered"] != "")]
    buckets: Counter = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for r in zc_all.itertuples(index=False):
        mine = zkey(r.zone_recovered)
        src = r.tx_zone
        if mine == src:
            buckets["일치"] += 1
            continue
        others = [zkey(x) for x in zlabels(zone, r.parcel)]
        if src in others:
            b = "필지_복수용도지역"
        elif zfamily(src) and zfamily(src) == zfamily(mine):
            b = "같은계열_세부등급차"
        elif not zfamily(src) or not zfamily(mine):
            b = "계열판정불가"
        else:
            b = "계열자체다름"
        buckets[b] += 1
        if len(examples[b]) < 5:
            examples[b].append(f"{r.asset_type} {r.parcel} 원장={src} / AL_D155={mine}")

    tot_z = sum(buckets.values())
    out["zone_mismatch_breakdown"] = {
        "note": "상가·공장은 원장에 용도지역이 있어 대조가 된다. "
        "'같은계열_세부등급차'와 '필지_복수용도지역'은 매칭 오류가 아니다.",
        "n": tot_z,
        "counts": dict(buckets),
        "pct": {k: _pct(v, tot_z) for k, v in buckets.items()},
        # 대표 라벨 하나가 아니라 그 필지의 용도지역 전부와 대조했을 때의 일치율.
        # 필지가 두 용도지역에 걸치는 게 흔하므로 이게 실제 정합도다.
        "agree_incl_multizone_pct": _pct(
            buckets["일치"] + buckets["필지_복수용도지역"], tot_z
        ),
        "examples": dict(examples),
    }

    # ---- A2 판정 출처 ----
    a2 = res[res["tier"] == "A2"]
    out["a2_land_source"] = {k: int(v) for k, v in a2["land_src"].value_counts().items()}

    out["overall"] = {
        "confirmed": int(ok.sum()),
        "confirmed_pct": _pct(int(ok.sum()), len(res)),
        "zone_dist_top": {
            k: int(v)
            for k, v in res.loc[ok, "zone_recovered"].replace("", pd.NA).dropna().value_counts().head(12).items()
        },
    }
    return out


# --------------------------------------------------------------------------- #
# 6. 시점 정합 비교
# --------------------------------------------------------------------------- #
def compare_snapshots(a: pd.DataFrame, b: pd.DataFrame, name_a: str, name_b: str) -> dict:
    m = a[["id", "asset_type", "contract_year", "tier", "fail"]].merge(
        b[["id", "tier", "fail"]], on="id", suffixes=("_a", "_b")
    )
    ok_a, ok_b = m["tier_a"].notna(), m["tier_b"].notna()
    gained = m[~ok_a & ok_b]
    lost = m[ok_a & ~ok_b]
    by_year = (
        m.assign(only_b=(~ok_a & ok_b), only_a=(ok_a & ~ok_b), both=(ok_a & ok_b))
        .groupby("contract_year")[["only_a", "only_b", "both"]]
        .sum()
        .astype(int)
    )
    return {
        "snapshot_a": name_a,
        "snapshot_b": name_b,
        "n": int(len(m)),
        "confirmed_a": int(ok_a.sum()),
        "confirmed_b": int(ok_b.sum()),
        "both": int((ok_a & ok_b).sum()),
        "only_a": int(len(lost)),
        "only_b": int(len(gained)),
        "union": int((ok_a | ok_b).sum()),
        "union_pct": _pct(int((ok_a | ok_b).sum()), len(m)),
        "gained_from_b_by_prev_fail": {
            k: int(v) for k, v in gained["fail_a"].value_counts().items()
        },
        "by_contract_year": {
            int(k): {c: int(v[c]) for c in v.index} for k, v in by_year.iterrows()
        },
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def snapshot_union(results: dict[str, pd.DataFrame]) -> dict:
    """스냅샷을 여러 개 쓰면 커버리지가 오르는가, 그리고 서로 다른 필지를 고르지는 않는가.

    커버리지만 보고 union 을 채택하면 안 된다. 두 스냅샷이 같은 거래에 다른 필지를
    지목하면 그건 최소 하나가 틀렸다는 직접 증거다 — 그 충돌률이 채택 여부를 가른다.
    """
    snaps = list(results)
    base = results[snaps[0]][["id", "asset_type", "contract_year"]].copy()
    for s in snaps:
        base = base.merge(
            results[s][["id", "parcel"]].rename(columns={"parcel": f"p_{s}"}), on="id", how="left"
        )
    cols = [f"p_{s}" for s in snaps]
    picks = base[cols]
    n_ok = picks.notna().sum(axis=1)
    union = int((n_ok >= 1).sum())

    multi = base[n_ok >= 2]
    conflict = 0
    for r in multi[cols].itertuples(index=False):
        vals = {v for v in r if isinstance(v, str)}
        if len(vals) > 1:
            conflict += 1

    # 계약연도 이전 최신 스냅샷을 쓰는 정책
    def policy_col(year: int | float) -> str:
        y = int(year) if pd.notna(year) else 2026
        for s in sorted(snaps, reverse=True):
            if int(s[:4]) <= y:
                return f"p_{s}"
        return f"p_{sorted(snaps)[0]}"

    years = base["contract_year"].tolist()
    picked = [base.at[i, policy_col(years[i])] for i in range(len(base))]
    policy_ok = sum(1 for v in picked if isinstance(v, str))

    return {
        "note": "union_pct 는 상한. conflict_pct 가 낮아야 채택할 수 있다.",
        "snapshots": snaps,
        "per_snapshot_pct": {
            s: _pct(int(results[s]["tier"].notna().sum()), len(results[s])) for s in snaps
        },
        "union": union,
        "union_pct": _pct(union, len(base)),
        "n_confirmed_by_2plus": int(len(multi)),
        "conflict": conflict,
        "conflict_pct_of_multi": _pct(conflict, len(multi)),
        "policy_year_aligned": policy_ok,
        "policy_year_aligned_pct": _pct(policy_ok, len(base)),
    }


AUDIT_COLS = [
    "id",
    "asset_type",
    "tier",
    "contract_year",
    "tx_lot",
    "tx_road",
    "gross_area",
    "land_area",
    "reg_addr",
    "reg_addr_road",
    "struct",
    "floors",
    "approve",
    "reg_use",
    "zone_recovered",
    "n_range",
    "n_exact",
    "판정",
]


def audit_sample(
    res: pd.DataFrame, zone: dict[str, list[str]], n: int, seed: int = 20260821
) -> pd.DataFrame:
    """구조·주소를 사람이 로드뷰·지도로 대조할 표본. asset_type × tier 층화 추출.

    '판정' 칸은 비워 둔다. 사람이 O/X 를 채우면 그게 구조 보강의 유일한 외부 근거다.
    """
    conf = res[res["tier"].notna()].copy()
    conf["zone_recovered"] = [zone_primary(zone, p) for p in conf["parcel"]]
    rng = pd.Series(range(len(conf))).sample(frac=1, random_state=seed).values
    conf = conf.iloc[rng]
    groups = list(conf.groupby(["asset_type", "tier"]))
    per = max(1, n // max(1, len(groups)))
    out = pd.concat([g.head(per) for _, g in groups])
    if len(out) < n:  # A2 표본이 적으면 A1 로 채운다
        rest = conf.drop(index=out.index).head(n - len(out))
        out = pd.concat([out, rest])
    out["판정"] = ""
    return out[AUDIT_COLS].sort_values(["asset_type", "tier", "id"])


TX_SQL = """
SELECT id, transaction_hash, asset_type, beopjungri_code, lot_number, road_name, zone_type,
       gross_area, land_area, building_age, contract_year, contract_month
FROM built_transactions
WHERE is_valid AND gross_area > 0 AND sigungu_code LIKE :sido_like
  AND is_partial_ownership IS NOT TRUE
  AND contract_year >= :min_year
"""


POLICIES = ("latest", "time", "time_fallback", "union")
KAIS_SAMPLE = REPO / "docs" / "lab" / "built_kais_recovery_sample.csv"


def _lot_tail(parcel: Any) -> str:
    if not isinstance(parcel, str) or "|" not in parcel:
        return ""
    return parcel.split("|", 1)[1].replace("번지", "").strip()


def kais_probe(res: pd.DataFrame) -> list[dict[str, Any]]:
    """KAIS 28건이 이 정책에서 어디로 붙는지. 표본 CSV가 없으면 빈 목록."""
    if not KAIS_SAMPLE.is_file():
        return []
    sample = pd.read_csv(KAIS_SAMPLE, dtype=str)
    by_id = res.set_index("id", drop=False)
    out = []
    for r in sample.itertuples(index=False):
        try:
            tid = int(r.id)
        except (TypeError, ValueError):
            continue
        if tid not in by_id.index:
            continue
        row = by_id.loc[tid]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        kais = str(getattr(r, "KAIS_실제지번", "") or "").strip()
        recovered = _lot_tail(row.get("parcel") if isinstance(row, dict) else row["parcel"])
        out.append(
            {
                "id": tid,
                "seq": str(getattr(r, "순서", "")),
                "kais": kais,
                "parcel": recovered,
                "snapshot_used": None if not isinstance(row, pd.Series) else row.get("snapshot_used"),
                "match_kais": bool(
                    kais and kais != "동일" and recovered == kais.replace("번지", "").strip()
                )
                or (kais == "동일" and recovered != ""),
            }
        )
    return out


def run(
    sido: str,
    snapshot: str,
    refresh: bool,
    use_zone: bool,
    sample: int = 0,
    policy: str = "time_fallback",
    compare_policies: bool = True,
    emit_enrichment: bool = False,
    apply_enrichment: bool = False,
    min_year: int = 2019,
) -> dict:
    eng = get_built_engine()
    with eng.connect() as conn:
        tx = pd.read_sql(
            text(TX_SQL),
            conn,
            params={"sido_like": f"{sido}%", "min_year": min_year},
        )
    print(f"[원장] {len(tx):,}건 (contract_year>={min_year})", flush=True)

    land_ledger = load_land_ledger(sido, refresh)
    if snapshot == "all":
        snaps = list(SNAPSHOTS)
    elif snapshot == "both":
        snaps = ["2024-09", PRIMARY]
    else:
        snaps = [snapshot]

    results: dict[str, pd.DataFrame] = {}
    metas: dict[str, dict] = {}
    for snap in snaps:
        title, summ, meta = load_register(sido, snap, refresh)
        parcels, idx = build_parcels(title, summ, land_ledger)
        meta["parcels"] = len(parcels)
        print(f"[{snap}] 필지 {len(parcels):,} · 표제부 {len(title):,}행", flush=True)
        results[snap] = match_all(tx, parcels, idx)
        metas[snap] = meta

    primary = PRIMARY if PRIMARY in snaps else snaps[-1]
    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    if len(snaps) == 1:
        res = results[snaps[0]].copy()
        res["snapshot_used"] = snaps[0]
        res["snapshot_via"] = "latest"
        policy_used = "latest"
    else:
        policy_used = policy
        res = apply_snapshot_policy(results, policy=policy_used, primary=primary)

    zone: dict[str, list[str]] = {}
    if use_zone:
        keep = {p for p in res["parcel"].dropna().unique()}
        if "rival_lots" in res.columns:
            for lots in res["rival_lots"].dropna():
                keep.update(lots)
        zone = load_zone(sido, keep, refresh)

    rep = report(
        res,
        zone,
        {"sido": sido, "primary_snapshot": primary, "policy": policy_used, **metas[primary]},
    )
    if len(snaps) > 1:
        rep["snapshot_compare"] = [
            compare_snapshots(results[s], results[primary], s, primary)
            for s in snaps
            if s != primary
        ]
        rep["snapshot_union"] = snapshot_union(results)
        if compare_policies:
            compare = {}
            for p in POLICIES:
                combined = apply_snapshot_policy(results, policy=p, primary=primary)
                compare[p] = policy_coverage(combined)
                compare[p]["kais"] = kais_probe(combined)
            rep["policy_compare"] = compare
    if emit_enrichment or apply_enrichment:
        labels = [
            zone.get(p, []) if isinstance(p, str) else []
            for p in res["parcel"]
        ]
        recs = to_enrichment_records(
            res,
            labels,
            coverage_scope="full" if use_zone else "A1_only",
            matched_cycle=datetime.now().strftime("%Y%m"),
        )
        CACHE.mkdir(exist_ok=True)
        applied = False
        apply_stats: dict | None = None
        if apply_enrichment:
            apply_stats = apply_enrichment_rows(eng, recs)
            applied = True
            print(
                f"[enrichment 적재] 시도 {apply_stats['attempted']:,} · "
                f"신규 {apply_stats['inserted']:,} · 동결유지 {apply_stats['already']:,}",
                flush=True,
            )
            rep["enrichment_apply"] = apply_stats
        epath = CACHE / f"enrichment_{sido}_{snapshot}.json"
        payload: dict[str, Any] = {
            "n": len(recs),
            "applied": applied,
            "apply": apply_stats,
        }
        if not apply_enrichment:
            payload["rows"] = recs
        epath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        rep["enrichment_preview"] = {"path": str(epath), "n": len(recs), "applied": applied}
        print(f"[enrichment JSON] {epath} · {len(recs):,}행", flush=True)
    if sample:
        path = CACHE / f"audit_sample_{sido}_{sample}.csv"
        audit_sample(res, zone, sample).to_csv(path, index=False, encoding="utf-8-sig")
        rep["audit_sample"] = str(path)
        print(f"[감사표본] {path}", flush=True)
    return rep


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="복합 마스킹 지번 복원 실측")
    ap.add_argument(
        "--sido",
        default="43",
        help="시도 코드 앞 2자리. all 이면 원장 전 시도 (이미 적재된 시도 제외)",
    )
    ap.add_argument(
        "--snapshot",
        default="all",
        choices=[*SNAPSHOTS, "both", "all"],
        help="표제부 본. 기본 all (거래시점 + 실패 시 보조)",
    )
    ap.add_argument(
        "--policy",
        default="time_fallback",
        choices=list(POLICIES),
        help="여러 스냅샷일 때 확정 규칙. 기본 time_fallback. latest·union은 대조군",
    )
    ap.add_argument("--refresh", action="store_true", help="캐시 무시하고 원본 재스캔")
    ap.add_argument("--no-zone", dest="zone", action="store_false", help="AL_D155 건너뜀")
    ap.add_argument("--sample", type=int, default=0, help="구조 감사용 표본 N건 CSV 추출")
    ap.add_argument("--no-compare-policies", action="store_true", help="4정책 대조 생략")
    ap.add_argument(
        "--emit-enrichment",
        action="store_true",
        help="확정 행 JSON 미리보기",
    )
    ap.add_argument(
        "--apply-enrichment",
        action="store_true",
        help="확정 행을 built_transaction_enrichment 에 INSERT. 기존 해시는 동결",
    )
    ap.add_argument(
        "--min-year",
        type=int,
        default=2019,
        help="원장 하한 계약연도. 제품 게이트 2019 (D-050). 연구용으로만 낮춤",
    )
    ap.add_argument("--out", default=None)
    return ap


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args()
    if args.sido.strip().lower() == "all":
        eng = get_built_engine()
        all_sidos = ledger_sidos(eng)
        done = sidos_with_enrichment(eng)
        todo = [s for s in all_sidos if s not in done]
        print(
            f"[전국] 원장 {all_sidos} · 이미 적재 {sorted(done)} · 이번 {todo}",
            flush=True,
        )
        if args.snapshot == "all":
            snaps = list(SNAPSHOTS)
        elif args.snapshot == "both":
            snaps = ["2024-09", PRIMARY]
        else:
            snaps = [args.snapshot]
        if todo:
            warm_register_caches(todo, snaps, args.refresh)
        summary: list[dict[str, Any]] = []
        for s in todo:
            print(f"\n======== sido {s} ========", flush=True)
            try:
                rep = run(
                    s,
                    args.snapshot,
                    False,
                    args.zone,
                    0,
                    args.policy,
                    compare_policies=False,
                    emit_enrichment=args.emit_enrichment or args.apply_enrichment,
                    apply_enrichment=args.apply_enrichment,
                    min_year=args.min_year,
                )
                apply = rep.get("enrichment_apply") or {}
                row: dict[str, Any] = {
                    "sido": s,
                    "ok": True,
                    "n_total": rep.get("n_total"),
                    "confirmed": (rep.get("overall") or {}).get("confirmed"),
                    "apply": apply,
                }
            except Exception as exc:
                print(f"[전국] {s} 실패: {exc}", flush=True)
                row = {"sido": s, "ok": False, "error": str(exc)}
            summary.append(row)
            CACHE.mkdir(exist_ok=True)
            (CACHE / "nationwide_enrich_progress.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        out = Path(args.out) if args.out else CACHE / "recover_all.json"
        CACHE.mkdir(exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"\nwrote {out}")
        return
    rep = run(
        args.sido,
        args.snapshot,
        args.refresh,
        args.zone,
        args.sample,
        args.policy,
        compare_policies=False if args.apply_enrichment else not args.no_compare_policies,
        emit_enrichment=args.emit_enrichment or args.apply_enrichment,
        apply_enrichment=args.apply_enrichment,
        min_year=args.min_year,
    )
    CACHE.mkdir(exist_ok=True)
    out = Path(args.out) if args.out else CACHE / f"recover_{args.sido}_{args.snapshot}.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print(f"\nwrote {out}")



if __name__ == "__main__":
    main()
