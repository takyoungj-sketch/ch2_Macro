"""Freeze local product numeric inputs in read-only, separate DB snapshots."""
import gzip
import json
import sys
from datetime import datetime, timezone

from sqlalchemy import bindparam, text
from ledger_consumer_input_preview import ROOT, OUT, LAB
from integrated_ledger_v2 import digest
from run_cheongju_integrated_ledger_v2 import file_hash
from ledger_supply_artifacts import write_gzip_atomic,write_json_atomic

sys.path.insert(0,str(ROOT/'pipeline'))
from collective.db_utils import get_collective_engine
from built.db_utils import get_built_engine

PATH=OUT/'product_numeric_baseline_20261005.json.gz'
MANIFEST=LAB/'cheongju_product_numeric_baseline.json'


def load():
    meta=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if file_hash(PATH)!=meta['gzip_sha256']:raise ValueError('Frozen numeric baseline changed')
    with gzip.open(PATH,'rt',encoding='utf-8') as f:payload=json.load(f)
    if digest(payload)!=meta['content_sha256']:raise ValueError('Frozen numeric content changed')
    return payload,meta


def snapshot(factory,queries):
    engine=factory()
    try:
        if engine.url.host not in ('localhost','127.0.0.1','::1'):raise ValueError('Local DB required')
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text("SET LOCAL statement_timeout='90s'"))
            result={'observation':dict(conn.execute(text('SELECT current_database() db,current_timestamp observed_at,txid_current_snapshot() snapshot')).one()._mapping)}
            result['observation']={k:str(v) for k,v in result['observation'].items()}
            for name,sql,params,expanding in queries:
                statement=text(sql).bindparams(*(bindparam(k,expanding=True) for k in expanding))
                result[name]=[json.loads(r[0],parse_float=str) for r in conn.execute(statement,params)]
    finally:engine.dispose()
    return result


def main():
    if PATH.exists() or MANIFEST.exists():
        payload,meta=load();print(json.dumps(meta,ensure_ascii=True));return
    path=OUT/'address_pair_impact_evidence.json.gz'
    with gzip.open(path,'rt',encoding='utf-8') as f:evidence=json.load(f)
    selected={p:[r for r in evidence[p] if r['window_years']==7] for p in ('residential','commercial')}
    queries=[]
    for p,stats,tx,key in [('residential','collective_building_stats','collective_transactions','building_key'),
                          ('commercial','collective_commercial_cluster_stats','collective_commercial_transactions','cluster_key')]:
        ids=sorted(r['id'] for r in selected[p]);params={'ids':ids}
        queries.append((p+'_stats',f'SELECT to_jsonb(s)::text FROM {stats} s WHERE s.id IN :ids ORDER BY s.id',params,['ids']))
        queries.append((p+'_transactions',f'''SELECT to_jsonb(t)::text FROM {tx} t JOIN {stats} s USING({key},asset_type)
           WHERE s.id IN :ids AND t.is_valid=true AND t.unit_price>0 AND t.contract_date BETWEEN s.period_start AND s.period_end ORDER BY t.id''',params,['ids']))
    keys=sorted({r['product_key'] for r in selected['residential']})
    for name,table,order in [('attributes','collective_building_attributes','building_key,asset_type,snapshot_ym'),
                             ('prices','collective_building_assessed_land_price','building_key,asset_type')]:
        queries.append((name,f'SELECT to_jsonb(s)::text FROM {table} s WHERE s.building_key IN :keys ORDER BY {order}',{'keys':keys},['keys']))
    payload={'collective':snapshot(get_collective_engine,queries)}
    payload['built']=snapshot(get_built_engine,[('transactions',"""SELECT jsonb_build_object('transaction',to_jsonb(t),'enrichment',to_jsonb(e))::text
       FROM built_transactions t LEFT JOIN built_transaction_enrichment e USING(transaction_hash)
       WHERE t.sigungu_code IN :districts ORDER BY t.transaction_hash""",{'districts':['43111','43112','43113','43114']},['districts'])])
    checks={'stats_cohort_preserved':all(len(payload['collective'][p+'_stats'])==len(selected[p]) for p in selected),
            'window_transaction_counts_match_stats':all(len(payload['collective'][p+'_transactions'])==sum(r['count'] for r in payload['collective'][p+'_stats']) for p in selected),
            'built_hashes_unique':len({r['transaction']['transaction_hash'] for r in payload['built']['transactions']})==len(payload['built']['transactions'])}
    if not all(checks.values()):raise AssertionError(checks)
    write_gzip_atomic(PATH,payload)
    meta={'frozen_at':datetime.now(timezone.utc).isoformat(),'content_sha256':digest(payload),'gzip_sha256':file_hash(PATH),
          'prior_scope_sha256':file_hash(path),'counts':{'collective':{k:len(v) for k,v in payload['collective'].items() if isinstance(v,list)},
          'built_transactions':len(payload['built']['transactions'])},'checks':checks,
          'db_observations':[payload[p]['observation'] for p in ('collective','built')],
          'limitations':['Separate local repeatable-read snapshots, not a synchronized production snapshot.','Frozen numeric inputs are never overwritten; refresh requires a new filename/version.']}
    write_json_atomic(MANIFEST,meta)
    print(json.dumps(meta,ensure_ascii=True))


if __name__=='__main__':main()
