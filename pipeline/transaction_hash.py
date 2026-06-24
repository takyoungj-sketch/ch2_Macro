"""land_transactions.transaction_hash 생성 (clean·dedupe·rehash 공용).

설계 원칙 (2026-06 확립):
  - hash 는 land_transactions 테이블에 *저장된* 필드만 사용 — 재처리 멱등성 보장
  - cancel_date·cancel_type·cancel_flag_raw 는 DB 에 저장되지 않으므로 hash 제외
    (is_cancelled BOOLEAN 만 사용)
  - lot_display 가 lot_number/main_number/sub_number 의 정규화 표현 — DB 저장값
  - area_sqm·total_price_10k 는 소수점 2자리로 정규화 — DB NUMERIC(xx,2) 와 일치
  - Excel 순번·raw_id 미포함 (재적재 멱등성)
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Hash 를 구성하는 논리 필드 목록 (문서화·테스트 참조용 SSOT)
# ---------------------------------------------------------------------------
HASH_FIELDS: list[str] = [
    "beopjungri_code",   # or sigungu_code / sigungu_name 폴백
    "contract_year",
    "contract_month",
    "contract_day",
    "lot_key",           # lot_display → lot_number → main_number|sub_number 우선순위
    "area_sqm",          # NUMERIC(12,2) 정규화: f"{v:.2f}"
    "total_price_10k",   # NUMERIC(14,2) 정규화: f"{v:.2f}"
    # positions 7, 8: 항상 "" (cancel_date·cancel_type 은 DB 미저장 — 2026-06 제외)
    "is_cancelled",      # "1" (True) 또는 "" (False/None)
]


def transaction_hash_key(
    *,
    beopjungri_code: str | None = None,
    sigungu_code: str | None = None,
    sigungu_name: str | None = None,
    contract_year: Any = "",
    contract_month: Any = "",
    contract_day: Any = "",
    lot_number: str | None = None,
    main_number: str | None = None,
    sub_number: str | None = None,
    lot_display: str | None = None,
    area_sqm: Any = "",
    total_price_10k: Any = "",
    # --- 아래 세 파라미터는 DEPRECATED: DB 에 저장되지 않아 hash 에서 제외 ---
    cancel_date: str | None = None,   # noqa: ARG001 — 하위 호환용, 사용 안 함
    cancel_type: str | None = None,   # noqa: ARG001 — 하위 호환용, 사용 안 함
    cancel_flag_raw: str | None = None,  # noqa: ARG001 — 하위 호환용, 사용 안 함
    # --- 정규 취소 플래그 ---
    is_cancelled: bool | None = None,
) -> str:
    """거래 1건의 논리 키 문자열 (SHA-256 입력).

    10-part 파이프 구분 포맷 유지 (2026-06 rehash 이후 DB 값과 호환):
      region | year | month | day | lot | area | price | "" | "" | cancel_flag
    """
    region_key = (
        _s(beopjungri_code) or _s(sigungu_code) or _s(sigungu_name) or ""
    )

    # lot_key: lot_display(DB 저장값)를 1순위, 원시 필드는 폴백
    lot_key = _s(lot_number)
    if not lot_key:
        mn, sn = _s(main_number), _s(sub_number)
        lot_key = (mn + "|" + sn) if mn else ""
    if not lot_key:
        lot_key = _s(lot_display) or ""

    # cancel_flag: is_cancelled boolean 만 사용 (cancel_date/type/flag_raw 무시)
    cancel_flag = "1" if is_cancelled else ""

    return "|".join([
        region_key,
        _s(contract_year),
        _s(contract_month),
        _s(contract_day),
        lot_key,
        _num2(area_sqm),
        _num2(total_price_10k),
        "",            # position 7: cancel_date 제외 (DB 미저장)
        "",            # position 8: cancel_type 제외 (DB 미저장)
        cancel_flag,   # position 9
    ])


def make_transaction_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def hash_from_series(row: Mapping[str, Any]) -> str:
    """단일 정규 hash 생성 함수 — clean·rehash·월간갱신 모두 이 함수를 사용한다.

    row 는 clean.py DataFrame 행 또는 land_transactions DB 행(dict)을 허용.
    lot_number / main_number 등 DB 미저장 필드가 없어도 lot_display 폴백으로 동작.
    """
    day = row.get("contract_day")
    if day is None or _is_missing(day):
        cd = row.get("contract_date")
        if cd is not None and hasattr(cd, "day"):
            day = cd.day

    return make_transaction_hash(
        transaction_hash_key(
            beopjungri_code=row.get("beopjungri_code"),
            sigungu_code=row.get("sigungu_code"),
            sigungu_name=row.get("sigungu_name"),
            contract_year=row.get("contract_year", ""),
            contract_month=row.get("contract_month", ""),
            contract_day=day if day is not None else "",
            lot_number=row.get("lot_number"),
            main_number=row.get("main_number"),
            sub_number=row.get("sub_number"),
            lot_display=row.get("lot_display"),
            area_sqm=row.get("area_sqm", ""),
            total_price_10k=row.get("total_price_10k", ""),
            # cancel_date / cancel_type / cancel_flag_raw 는 전달해도 무시됨
            is_cancelled=bool(row.get("is_cancelled")) if row.get("is_cancelled") is not None else False,
        )
    )


# ---------------------------------------------------------------------------
# 내부 유틸
# ---------------------------------------------------------------------------

def _s(v: Any) -> str:
    """값을 문자열로 변환. None·NaN·pd.NA 는 모두 "" 반환."""
    if v is None:
        return ""
    # float NaN
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return ""
    # pd.NA (pandas 확장 결측값 — isinstance(pd.NA, float) == False)
    try:
        import pandas as _pd  # 선택적 의존
        if v is _pd.NA:
            return ""
    except ImportError:
        pass
    # numpy scalar NaN
    try:
        import numpy as _np
        if isinstance(v, _np.floating) and _np.isnan(v):
            return ""
    except ImportError:
        pass
    s = str(v).strip()
    # str(float('nan')) == "nan" 잔여 케이스
    if s.lower() in ("nan", "nat", "<na>", "none", "null"):
        return ""
    return s


def _num2(v: Any) -> str:
    """숫자를 소수점 2자리 문자열로 정규화 (DB NUMERIC(xx,2) 와 일치).

    - float 570.18 → "570.18"
    - Decimal('570.10') → "570.10"
    - 빈값/None/NaN → ""
    """
    if v is None or v == "":
        return ""
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return ""
        return f"{f:.2f}"
    except (TypeError, ValueError):
        return _s(v)


def _is_missing(v: Any) -> bool:
    """NaN·pd.NA·None 등 결측값인지 판별."""
    return _s(v) == ""
