"""행정명 정규화 — 적재 시 개편 후 시도명으로 맞춘다(집합 2단계 C-02 재발 방지).

2026-07 광주·전남 통합 이후 원장 addr1은 「전남광주통합특별시」 하나다. 옛 원천 파일(raw long term 등)이
옛 시도명을 그대로 갖고 있어 addr1이 갈라지고, addr1이 들어가는 단지·cluster 키도 갈라졌다.
코드 조회용 별칭(clean._SIDO_NAME_ALIASES)과 달리 이 함수는 저장되는 addr1 문자열 자체를 바꾼다.
"""
from __future__ import annotations

import pandas as pd

LEGACY_SIDO_TO_CURRENT: dict[str, str] = {
    "광주광역시": "전남광주통합특별시",
    "전라남도": "전남광주통합특별시",
}


def canonical_sido_name(name: object) -> object:
    if not isinstance(name, str):
        return name
    s = name.strip()
    return LEGACY_SIDO_TO_CURRENT.get(s, name)


def normalize_addr1_column(df: pd.DataFrame, col: str = "addr1") -> pd.DataFrame:
    """addr1의 옛 시도명을 개편 후 이름으로(제자리 변경 아님, 사본 반환)."""
    if df.empty or col not in df.columns:
        return df
    s = df[col]
    hit = s.isin(LEGACY_SIDO_TO_CURRENT.keys())
    if not hit.any():
        return df
    out = df.copy()
    out.loc[hit, col] = s[hit].map(LEGACY_SIDO_TO_CURRENT)
    return out
