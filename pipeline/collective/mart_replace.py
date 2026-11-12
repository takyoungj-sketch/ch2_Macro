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


LEGACY_ADDR1 = ("광주광역시", "전라남도")


def prune_annual(engine, annual_table: str, *, batch_id: str, asset_type: str | None = None) -> dict:
    """annual 정리(T 결정 2026-11-12, Phase C 조건 2). 이번 빌드(batch_id)가 쓴 뒤 호출.

    ① 2021년 이후: 이번 계산(batch_id)이 쓰지 않은 행만 삭제
    ② 2019~2020: 호남 옛 시도명(addr1) 이중 행만 삭제 — 그 밖의 묵은 행은 남기고 stale_annual_report 로 보고
    ③ 2010~2018: 삭제하지 않는다
    """
    extra = " AND asset_type = :t" if asset_type else ""
    params: dict = {"b": batch_id, "leg": list(LEGACY_ADDR1)}
    if asset_type:
        params["t"] = asset_type
    with engine.begin() as c:
        n1 = c.execute(text(f"DELETE FROM {annual_table} WHERE contract_year >= 2021 "
                            f"AND batch_id IS DISTINCT FROM :b{extra}"), params).rowcount or 0
        n2 = c.execute(text(f"DELETE FROM {annual_table} WHERE contract_year IN (2019, 2020) AND addr1 = ANY(:leg) "
                            f"AND batch_id IS DISTINCT FROM :b{extra}"), params).rowcount or 0
    out = {"deleted_2021_plus": int(n1), "deleted_2019_2020_legacy_sido": int(n2), "deleted_2010_2018": 0}
    log.info("prune-annual %s: %s", annual_table, out)
    return out


def stale_annual_report(conn, annual_table: str, ledger_table: str, key_col: str, *, batch_id: str) -> list[tuple]:
    """2019~2020 에 남은 묵은 행(이번 batch 가 아닌 행)을 유형·연도·시도·출처별로.

    출처 = 그 행을 쓴 batch 의 연도 범위로 판단: 2010~2018만 쓴 batch → 장기 ingest, 그 밖 → 원장 빌더(작성일).
    원장 근거 = 같은 키·연도 유효 거래가 지금 원장에 있는지.
    """
    sql = f"""
    WITH b AS (SELECT batch_id, min(contract_year) y0, max(contract_year) y1, min(computed_at)::date d
               FROM {annual_table} GROUP BY batch_id)
    SELECT a.asset_type, a.contract_year, a.addr1,
           CASE WHEN b.y1 <= 2018 THEN '장기 ingest' ELSE '원장 빌더' END AS source, b.d AS written,
           EXISTS (SELECT 1 FROM {ledger_table} t WHERE t.{key_col} = a.{key_col} AND t.asset_type = a.asset_type
                   AND t.contract_year = a.contract_year) AS ledger_has_key,
           count(*) AS rows, sum(a.count)::bigint AS tx
    FROM {annual_table} a JOIN b USING (batch_id)
    WHERE a.contract_year IN (2019, 2020) AND a.batch_id IS DISTINCT FROM :b
    GROUP BY 1,2,3,4,5,6 ORDER BY 1,2,3,4,5,6
    """
    return [tuple(r) for r in conn.execute(text(sql), {"b": batch_id}).all()]
