"""Read-only schema and coverage audit for the Cheongju ledger integration review."""
import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
from parcel_master.db_utils import get_parcel_engine
from built.db_utils import get_built_engine
from collective.db_utils import get_collective_engine

DISTRICTS = "('43111','43112','43113','43114')"


def read(factory, queries):
    engine = factory()
    # This audit is for the local research environment only.
    if engine.url.host not in ('localhost', '127.0.0.1', '::1'):
        raise RuntimeError('Local database required')
    results = {}
    for name, sql in queries.items():
        try:
            with engine.connect() as conn:
                conn.execute(text('SET TRANSACTION READ ONLY'))
                conn.execute(text("SET LOCAL statement_timeout = '30s'"))
                results[name] = [dict(row._mapping) for row in conn.execute(text(sql))]
        except Exception as exc:
            # Do not serialize connection strings, SQL parameters or exception messages.
            results[name] = {'error_type': type(exc).__name__}
    engine.dispose()
    return results


def main():
    columns = "SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN {tables} ORDER BY table_name,ordinal_position"
    report = {'run_date': '2026-10-04', 'scope': 'Cheongju four districts; local read-only audit'}
    report['parcel_master'] = read(get_parcel_engine, {
        'columns': columns.format(tables="('building','parcel','ledger_snapshot','parcel_land_price')"),
        'building_snapshots': f"SELECT snapshot,ledger_kind,count(*) AS rows,count(DISTINCT mgmt_pk) AS building_keys,count(DISTINCT pnu) AS parcels FROM building WHERE sido_code='43' AND substring(beopjungri_code,1,5) IN {DISTRICTS} GROUP BY snapshot,ledger_kind ORDER BY snapshot,ledger_kind",
        'multi_building_parcels': f"SELECT snapshot,count(*) AS parcels_with_multiple_buildings FROM (SELECT snapshot,pnu FROM building WHERE sido_code='43' AND substring(beopjungri_code,1,5) IN {DISTRICTS} GROUP BY snapshot,pnu HAVING count(DISTINCT mgmt_pk)>1) s GROUP BY snapshot ORDER BY snapshot",
    })
    report['built_stats'] = read(get_built_engine, {
        'columns': columns.format(tables="('built_transactions','built_transaction_enrichment')"),
        'enrichment_coverage': f"SELECT t.asset_type,count(*) AS transactions,count(e.transaction_hash) AS enriched,count(NULLIF(btrim(e.bldrgst_pk),'')) AS enriched_with_building_pk FROM built_transactions t LEFT JOIN built_transaction_enrichment e USING(transaction_hash) WHERE t.sigungu_code IN {DISTRICTS} GROUP BY t.asset_type ORDER BY t.asset_type",
    })
    report['collective_stats'] = read(get_collective_engine, {
        'columns': columns.format(tables="('building_stats','collective_building_attributes','collective_building_assessed_land_price','commercial_clusters','collective_commercial_transactions')"),
        'assessed_mart_years': "SELECT asset_type,assessed_land_price_year,count(*) AS rows FROM collective_building_assessed_land_price GROUP BY asset_type,assessed_land_price_year ORDER BY asset_type,assessed_land_price_year",
    })
    path = ROOT / 'docs/lab/cheongju_building_integration_audit_20261004.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    compact = {db: {k:v for k,v in values.items() if k!='columns'} for db,values in report.items() if isinstance(values,dict)}
    print(json.dumps(compact,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
