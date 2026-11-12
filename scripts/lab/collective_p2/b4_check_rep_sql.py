"""Phase B-4 확인 — 빌더 SQL(대표 주소)이 A-3 측정 결과와 같은지(읽기 전용, 한 시도)."""
import importlib.util
import sys
import pandas as pd
from sqlalchemy import text
from _db import OUT, ROOT, engine
sys.path.insert(0, str(ROOT / "pipeline")); sys.path.insert(0, str(ROOT / "pipeline" / "collective"))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

bcs = load("bcs", ROOT / "pipeline" / "build_collective_building_stats.py")
pls = load("pls", ROOT / "pipeline" / "build_collective_presale_lifetime_stats.py")
rbs = load("rbs", ROOT / "pipeline" / "rent" / "build_building_stats.py")
rep = pd.read_pickle(OUT / "a3_rep5.pkl")
A1 = "충청북도"
with engine().connect() as c:
    ps, pe = c.execute(text("select min(period_start), max(period_end) from collective_building_stats where as_of_month='2026-10-01' and window_years=5")).one()
    df = pd.read_sql(text(bcs.ROLLING_SQL.format(asset_clause="", addr1_clause="AND addr1 = :addr1")), c, params={"p_start": ps, "p_end": pe, "addr1": A1})
    an = pd.read_sql(text(bcs.ANNUAL_SQL.format(asset_clause="AND asset_type = 'apartment'", addr1_clause="AND addr1 = :addr1")), c, params={"addr1": A1})
    pr = pd.read_sql(text(pls.LIFETIME_SQL.format(addr1_clause="AND addr1 = :addr1")), c, params={"addr1": A1})
cols = ["building_key", "asset_type", "addr3", "addr4", "addr5", "beopjungri_code", "lot_number", "road_name"]
m = df[cols].merge(rep[cols], on=["building_key", "asset_type"], suffixes=("", "_a3"))
diff = sum(int((m[c].fillna("") != m[c + "_a3"].fillna("")).sum()) for c in cols[2:])
print("rolling rows", len(df), "matched to A-3", len(m), "field diffs", diff, "prices ok", bool(df.prices.map(len).gt(0).all()))
print("annual rows", len(an), "presale rows", len(pr), "cols", list(an.columns)[:8])
with engine("rent").connect() as c:
    r = pd.read_sql(text(rbs.GROUP_SQL.format(addr1_clause="AND addr1 = :addr1", asset_clause="")), c, params={"p_start": ps, "p_end": pe, "addr1": "세종특별자치시"})
print("rent rows", len(r), list(r.columns)[:6])
