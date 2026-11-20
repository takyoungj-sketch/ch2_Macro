"""집합 2단계 P4 — C-2 로 나뉜 아파트 조각의 표시 이름 「단지명 (YYYY년 준공)」.

- 표시만 바꾼다. `display_name`(검색·정렬·키 계산에 씀)과 키는 그대로 두고 `display_label` 을 더한다.
- 대상: 연결표(collective_building_key_map)에서 reason 에 c2 가 든 행의 옛 키(본 조각)와 새 키(조각) 중 아파트.
  연결표는 key_remap 의 캐시(KeyMapCache)를 같이 쓴다 — 표가 없거나 비면 아무 키도 대상이 아니다(라벨 없음).
- 연립·오피스텔·분양권은 이번 범위 밖이다(지시: 분할된 아파트 조각에만).
"""
from __future__ import annotations

import threading
from typing import Any, Iterable, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from .key_remap import CACHE, KeyMapCache, split_entries

LABEL_ASSETS = frozenset({"apartment"})
_memo: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def c2_fragment_keys(cache: KeyMapCache | None = None, app: str = "collective") -> frozenset[str]:
    """C-2 조각 키 집합(본 조각 옛 키 + 조각 새 키). 연결표가 바뀌기 전까지 다시 계산하지 않는다."""
    m = (cache or CACHE).get(app)
    with _lock:
        slot = _memo.get(app)
        if slot and slot["src"] is m:
            return slot["keys"]
    keys: set[str] = set()
    for old, entries in (m or {}).items():
        _, c2 = split_entries(entries)
        if c2:
            keys.add(old)
            keys.update(t[0] for t in c2)
    out = frozenset(keys)
    with _lock:
        _memo[app] = {"src": m, "keys": out}
    return out


def c2_label(building_key: str, display_name: Optional[str], asset_type: Optional[str],
             building_year: Optional[int], *, keys: frozenset[str] | None = None) -> Optional[str]:
    """조각 아파트면 「단지명 (YYYY년 준공)」, 아니면 None(화면은 display_name 을 쓴다)."""
    if (asset_type or "") not in LABEL_ASSETS or not display_name or building_year is None:
        return None
    try:
        y = int(building_year)
    except (TypeError, ValueError):
        return None
    if y <= 0:
        return None
    ks = c2_fragment_keys() if keys is None else keys
    if building_key not in ks:
        return None
    return f"{display_name} ({y}년 준공)"


def c2_labels_for_keys(conn: Connection, building_keys: Iterable[str], *,
                       keys: frozenset[str] | None = None) -> dict[str, str]:
    """거래 원장에서 키별 이름·준공연도(최빈)로 라벨을 만든다 — 목록 행이 없는 곳(CSV 내보내기 등)에서 쓴다."""
    ks = c2_fragment_keys() if keys is None else keys
    want = sorted({k for k in building_keys if k in ks})
    if not want:
        return {}
    rows = conn.execute(text(
        """SELECT building_key, max(display_name) AS display_name, max(asset_type) AS asset_type,
                  mode() WITHIN GROUP (ORDER BY building_year) AS building_year
           FROM collective_transactions WHERE building_key IN :k AND is_valid GROUP BY 1""").bindparams(
        bindparam("k", expanding=True)), {"k": want}).mappings().all()
    out: dict[str, str] = {}
    for r in rows:
        lab = c2_label(str(r["building_key"]), r["display_name"], r["asset_type"], r["building_year"], keys=ks)
        if lab:
            out[str(r["building_key"])] = lab
    return out
