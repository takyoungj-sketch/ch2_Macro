"""Phase 1 보고용 — expand_beopjungri_codes 가 mart(as_of_month 무관 전체)를 훑는 영향 측정(읽기 전용, 코드 변경 없음).

단위(addr1, addr2, addr3, addr4)별 확장 코드 집합을 '전체 as_of' vs '최신 as_of' 로 비교한다.
출력: 표준 출력 요약(지번 없음).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402

eng = create_engine(settings.collective_database_url,
                    connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=600000"})
with eng.connect() as c:
    months = [r[0] for r in c.execute(text("select distinct as_of_month from collective_building_stats order by 1")).fetchall()]
    df = pd.DataFrame(c.execute(text(
        """select addr1, coalesce(addr2,'') a2, coalesce(addr3,'') a3, coalesce(addr4,'') a4,
                  btrim(beopjungri_code::text) code, max(as_of_month) last_as_of
           from collective_building_stats where beopjungri_code is not null
           group by 1,2,3,4,5""")).fetchall(), columns=["a1", "a2", "a3", "a4", "code", "last"])
latest = max(months)
units = df.groupby(["a1", "a2", "a3", "a4"])
n_units = units.ngroups
stale = df[df["last"] < latest]
stale_units = stale.groupby(["a1", "a2", "a3", "a4"]).ngroups
print(f"as_of_month {len(months)}개 ({months[0]} ~ {latest}) · 확장 단위 {n_units:,}개")
print(f"최신 as_of 에 없는 (단위, 코드) 쌍 {len(stale):,}개 · 그런 쌍이 있는 단위 {stale_units:,}개")
