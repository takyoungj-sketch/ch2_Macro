"""mart 재생성 보조 — 같은 as_of 를 다시 만들 때 옛 키 행이 남지 않게(집합 2단계 Phase B).

빌더는 UPSERT 만 해서, 키가 바뀐 뒤 같은 as_of 를 다시 빌드하면 옛 키 행이 그대로 남는다
(호남 옛 이름 7년 행·분할 전 키 행 → 이중 집계). 월간 cycle 은 새 as_of 라 영향이 없어 기본은 끈다.
빌더 옵션 --replace-as-of / --prune-annual 로만 동작한다.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

log = logging.getLogger(__name__)


def delete_as_of(engine, table: str, *, as_of, windows: list[int], asset_type: str | None = None,
                 addr1: str | None = None) -> int:
    """table 의 as_of_month·window_years 행을 지운다(빌드 직전). addr1 한정 빌드면 addr1 열이 있어야 한다."""
    where = ["as_of_month = :a", "window_years = ANY(:w)"]
    params: dict = {"a": as_of, "w": list(windows)}
    if asset_type:
        where.append("asset_type = :t")
        params["t"] = asset_type
    if addr1:
        with engine.connect() as c:
            has = c.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name=:t AND column_name='addr1'"),
                            {"t": table}).first()
        if not has:
            raise SystemExit(f"--replace-as-of 와 --addr1 을 함께 쓸 수 없음({table}에 addr1 없음)")
        where.append("addr1 = :addr1")
        params["addr1"] = addr1
    with engine.begin() as c:
        r = c.execute(text(f"DELETE FROM {table} WHERE {' AND '.join(where)}"), params)
    n = int(r.rowcount or 0)
    log.info("replace-as-of: %s 에서 %d행 삭제(as_of=%s windows=%s)", table, n, as_of, windows)
    return n


def prune_annual(engine, annual_table: str, ledger_table: str, key_col: str, *, min_year: int = 2019,
                 ledger_filter: str = "t.is_valid = true AND t.unit_price IS NOT NULL AND t.unit_price > 0",
                 asset_type: str | None = None) -> int:
    """원장에 근거가 없는 annual 행(min_year 이후) 삭제. 2010~2018 장기 annual(원장 밖 원천)은 건드리지 않는다."""
    extra = "AND a.asset_type = :t" if asset_type else ""
    sql = f"""
        DELETE FROM {annual_table} a
        WHERE a.contract_year >= :y {extra}
          AND NOT EXISTS (
            SELECT 1 FROM {ledger_table} t
            WHERE t.{key_col} = a.{key_col} AND t.asset_type = a.asset_type
              AND t.contract_year = a.contract_year AND {ledger_filter})
    """
    params: dict = {"y": min_year}
    if asset_type:
        params["t"] = asset_type
    with engine.begin() as c:
        r = c.execute(text(sql), params)
    n = int(r.rowcount or 0)
    log.info("prune-annual: %s 에서 원장 근거 없는 %d행 삭제(>= %d)", annual_table, n, min_year)
    return n
