"""Real FastAPI requests and PostgreSQL queries on connection-local frozen fixtures."""
import json
import logging
import sys
import urllib.request
from collections import Counter
from contextlib import ExitStack
from time import perf_counter
from pathlib import Path

from ledger_consumer_input_preview import ROOT,OUT,LAB
from ledger_supply_bundle import load_verified_supply,verify_manifest,sha
from ledger_supply_artifacts import write_gzip_atomic,write_json_atomic
from ledger_http_isolation import TemporaryProductDB,fixture_rows,pagination_check
from integrated_ledger_v2 import digest

sys.path.insert(0,str(ROOT/'pipeline'));sys.path.insert(0,str(ROOT/'backend'))
from collective.db_utils import get_collective_engine
from built.db_utils import get_built_engine
from sqlalchemy import text,bindparam
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.collective.db import get_collective_db
from app.built.db import get_built_db

logging.getLogger('httpx').setLevel(logging.WARNING)
TOKEN='ledger-audit-process-only-token'
PATHS={'residential':'/api/collective/buildings','commercial':'/api/collective/commercial/clusters','built':'/api/built/transactions'}


def live_health():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=5) as response:return {'status':response.status}
    except Exception as exc:return {'status':None,'error_type':type(exc).__name__}


def cluster_reference(frozen):
    ids=sorted({r['cluster_id'] for r in frozen['collective']['commercial_transactions']})
    engine=get_collective_engine()
    try:
        if engine.url.host not in ('localhost','127.0.0.1','::1'):raise ValueError('Local reference DB required')
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            sql=text('SELECT to_jsonb(c)::text FROM public.commercial_clusters c WHERE id IN :ids ORDER BY id').bindparams(bindparam('ids',expanding=True))
            rows=[json.loads(r[0],parse_float=str) for r in conn.execute(sql,{'ids':ids})]
            if {r['id'] for r in rows}!=set(ids):raise ValueError('Commercial cluster reference missing')
            return rows
    finally:engine.dispose()


def cases(frozen):
    stats=frozen['collective']['residential_stats'];province,city=stats[0]['addr1'],stats[0]['addr2']
    common={'addr1':province,'addr2':city,'window_years':7,'page_size':37}
    result=[]
    def add(name,kind,params,status=200,auth='valid'):
        result.append({'name':name,'path':PATHS[kind],'params':params,'expected_status':status,'auth':auth})
    for kind in PATHS:
        base=dict(common) if kind!='built' else {'addr1':province,'addr2':city,'page_size':37}
        add(kind+'_missing_token',kind,base,401,'missing');add(kind+'_wrong_token',kind,base,401,'wrong')
        add(kind+'_invalid_page',kind,{**base,'page':0},422)
        add(kind+'_invalid_page_size',kind,{**base,'page_size':501},422)
        add(kind+'_empty_region',kind,{**base,'addr2':'없는시군구'},200)
    for kind,sorts in [('residential',('count','mean','display_name','address','households')),('commercial',('count','mean','display_label'))]:
        for sort in sorts:
            for page in (1,2):add(kind+'_'+sort+'_page'+str(page),kind,{**common,'sort':sort,'page':page})
        add(kind+'_missing_city',kind,{'window_years':7},400)
        add(kind+'_invalid_years',kind,{**common,'contract_year_from':2026,'contract_year_to':2025},400)
        add(kind+'_invalid_sort',kind,{**common,'sort':'invalid'},422)
        years=[r['contract_year'] for r in frozen['collective'][kind+'_transactions'] if r['contract_year']]
        year=max(years)
        add(kind+'_live_year',kind,{**common,'contract_year_from':year,'contract_year_to':year})
        source=stats if kind=='residential' else frozen['collective']['commercial_stats']
        gu=next(r['addr3'] for r in source if r['addr3']);leaf=next(r['addr4'] for r in source if r['addr4'])
        add(kind+'_gu_filter',kind,{**common,'addr3_list':[gu]})
        add(kind+'_leaf_filter',kind,{**common,'addr4_list':[leaf]})
        add(kind+'_addr_unit_filter',kind,{**common,'region_addrs':[province+'|'+city+'|'+gu]})
    for asset in ('apartment','rowhouse','officetel','presale'):add('residential_'+asset,'residential',{**common,'asset_type':asset})
    for asset in ('collective_shop','collective_factory'):add('commercial_'+asset,'commercial',{**common,'asset_type':asset})
    built_base={'addr1':province,'addr2':city,'page_size':37}
    for enrich in (False,True):
        add('built_enrich_'+str(enrich),'built',{**built_base,'enrich':str(enrich).lower()})
        add('built_area_'+str(enrich),'built',{**built_base,'enrich':str(enrich).lower(),'gross_area_min':100,'gross_area_max':1000})
    zones=next(r['transaction']['zone_type'] for r in frozen['built']['transactions'] if r['transaction'].get('zone_type'))
    add('built_zone_ledger','built',{**built_base,'zone_types':[zones]})
    add('built_zone_enriched','built',{**built_base,'enrich':'true','zone_types':[zones]})
    for asset in sorted({r['transaction']['asset_type'] for r in frozen['built']['transactions']}):
        add('built_asset_'+asset,'built',{**built_base,'asset_type':asset})
    return result,province,city


def execute(client,case):
    headers={} if case['auth']=='missing' else {'X-Api-Token':TOKEN if case['auth']=='valid' else 'wrong-audit-token'}
    started=perf_counter();response=client.get(case['path'],params=case['params'],headers=headers)
    payload=response.json()
    if response.status_code!=case['expected_status']:raise AssertionError((case['name'],response.status_code,payload))
    if case['name'].endswith('_empty_region') and payload['total']!=0:raise AssertionError('Empty region returned rows')
    if response.status_code==200:
        params=case['params'];items=payload['items'];asset=params.get('asset_type')
        if asset and any(row['asset_type']!=asset for row in items):raise AssertionError('Asset filter leaked another type')
        if len(items)>params.get('page_size',100):raise AssertionError('Page size was not applied')
        if case['path']==PATHS['built']:
            ordering=[(r['contract_date'] or '',r['id']) for r in items]
            if ordering!=sorted(ordering,reverse=True):raise AssertionError('Transaction ordering changed')
            for row in items:
                for field in ('gross_area',):
                    for suffix,op in (('_min',lambda a,b:a>=b),('_max',lambda a,b:a<=b)):
                        if field+suffix in params and (row[field] is None or not op(row[field],params[field+suffix])):
                            raise AssertionError('Numeric filter failed')
        elif params.get('sort')=='count' and [r['count'] for r in items]!=sorted((r['count'] for r in items),reverse=True):
            raise AssertionError('Count sort failed')
    return {'status':response.status_code,'body':payload,'elapsed_seconds':perf_counter()-started}


def main():
    started=perf_counter();frozen,paired,manifest_hash=load_verified_supply(ROOT)
    health=live_health();reference=cluster_reference(frozen);requests,province,city=cases(frozen)
    old_token=settings.api_token;overrides=dict(app.dependency_overrides);results={};sql={};isolation={}
    snapshot_scope={}
    for kind in ('residential','commercial'):
        stats=frozen['collective'][kind+'_stats'];head=max(r['as_of_month'] for r in stats)
        snapshot_scope[kind]={'latest_product_mart_month':head,'frozen_rows':len(stats),
                             'latest_month_rows':sum(r['as_of_month']==head for r in stats),
                             'older_month_rows':sum(r['as_of_month']!=head for r in stats)}
    try:
        settings.api_token=TOKEN
        for branch in ('legacy','compatible'):
            collective,built=fixture_rows(frozen,paired,branch,reference)
            with ExitStack() as stack:
                c=stack.enter_context(TemporaryProductDB(get_collective_engine(),collective))
                b=stack.enter_context(TemporaryProductDB(get_built_engine(),built))
                app.dependency_overrides[get_collective_db]=c.dependency
                app.dependency_overrides[get_built_db]=b.dependency
                client=stack.enter_context(TestClient(app))
                rows={case['name']:execute(client,case) for case in requests}
                for kind in PATHS:
                    modes=(False,True) if kind=='built' else (False,)
                    for enrich in modes:
                        params={'addr1':province,'addr2':city,'page_size':500}
                        if kind!='built':params.update(window_years=7)
                        else:params['enrich']=str(enrich).lower()
                        items=[];page=1;total=None
                        while total is None or len(items)<total:
                            case={'name':kind+'_full_page_'+str(enrich)+'_'+str(page),'path':PATHS[kind],
                                  'params':{**params,'page':page},'expected_status':200,'auth':'valid'}
                            response=execute(client,case);rows[case['name']]=response
                            body=response['body']
                            if total is not None and body['total']!=total:raise ValueError('Pagination total changed')
                            total=body['total'];items.extend(body['items']);page+=1
                            if not body['items'] and len(items)<total:raise ValueError('Pagination ended early')
                        pagination_check(items,total,'id' if kind=='built' else 'building_key' if kind=='residential' else 'cluster_key')
                        if kind!='built':
                            key='building_key' if kind=='residential' else 'cluster_key'
                            expected={(r[key],r['asset_type']) for r in frozen['collective'][kind+'_stats']
                                      if r['as_of_month']==snapshot_scope[kind]['latest_product_mart_month']}
                            if {(r[key],r['asset_type']) for r in items}!=expected:
                                raise ValueError('Latest product mart key coverage differs: '+kind)
                        case={'name':kind+'_past_last_'+str(enrich),'path':PATHS[kind],
                              'params':{**params,'page':page+1},'expected_status':200,'auth':'valid'}
                        rows[case['name']]=execute(client,case)
                        if rows[case['name']]['body']['items']:raise ValueError('Past-last page is not empty')
                results[branch]=rows
                sql[branch]={'collective':dict(c.sql_counts),'built':dict(b.sql_counts)}
                isolation[branch]={'collective_temp_resolution':c.resolution,'built_temp_resolution':b.resolution,
                     'request_transactions_read_only':True,'temporary_rows':{**{k:len(v) for k,v in collective.items()},**{k:len(v) for k,v in built.items()}}}
            print('Completed HTTP branch',branch,len(rows),flush=True)
    finally:
        settings.api_token=old_token;app.dependency_overrides.clear();app.dependency_overrides.update(overrides)
    if verify_manifest(ROOT)[1]!=manifest_hash:raise ValueError('Supply changed during HTTP comparison')
    left,right=results['legacy'],results['compatible']
    differences=[name for name in left if left[name]['status']!=right[name]['status'] or left[name]['body']!=right[name]['body']]
    if differences:raise AssertionError('HTTP response differences: '+','.join(differences))
    payload={'supply_manifest_sha256':manifest_hash,'cluster_reference':reference,'request_cases':requests,'results':results,'isolation':isolation,'sql_hash_counts':sql}
    path=OUT/'product_http_sql_replay.json.gz';write_gzip_atomic(path,payload)
    report={'audit':'cheongju-frozen-http-postgresql-v1','supply_manifest_sha256':manifest_hash,
       'cases_per_branch':len(left),'http_requests_total':len(left)+len(right),'response_differences':len(differences),
       'status_counts_per_branch':dict(Counter(str(r['status']) for r in left.values())),
       'sql_queries_by_branch':{branch:{domain:sum(counts.values()) for domain,counts in domains.items()} for branch,domains in sql.items()},
       'temporary_isolation':isolation,'cluster_reference_sha256':digest(reference),'live_api_health_before_run':health,
       'product_mart_snapshot_scope':snapshot_scope,
       'full_page_totals':{name:row['body']['total'] for name,row in left.items() if '_full_page_' in name and name.endswith('_1')},
       'checks':{'http_status_and_bodies_equal':True,'missing_wrong_token_rejected':True,'query_validation_and_domain_errors_checked':True,
          'all_pages_complete_without_duplicate_keys':True,'past_last_and_empty_region_checked':True,'actual_postgresql_temp_tables_used':True,
          'request_transactions_read_only':True,'source_generation_unchanged':True,'asset_numeric_filters_and_transaction_sort_checked':True,
          'all_latest_product_mart_keys_returned':True},
       'gzip_sha256':sha(path),'payload_content_sha256':digest(payload),'production_apply':False,'elapsed_seconds':perf_counter()-started,
       'implementation_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in (
           ROOT/'pipeline/parcel_master/ledger_http_isolation.py',Path(__file__),ROOT/'backend/app/main.py',
           ROOT/'backend/app/collective/router.py',ROOT/'backend/app/collective/building_stats_query.py',ROOT/'backend/app/collective/danji_attributes.py',
           ROOT/'backend/app/collective/type_siblings.py',ROOT/'backend/app/collective_commercial/router.py',ROOT/'backend/app/collective_commercial/cluster_stats_query.py',
           ROOT/'backend/app/built/router.py',ROOT/'backend/app/built/transaction_scope.py',ROOT/'backend/app/built/enrichment_join.py')},
       'limitations':['Actual FastAPI TestClient ASGI requests and PostgreSQL SQL; no TCP/nginx/frontend browser or production authentication credential test.',
           'Frozen selected product cohort and seven-year transaction scope, not all city transactions or all API endpoints/windows.',
           'Annual counts derived from frozen transactions for gate lookup; commercial cluster metadata read from local DB once and shared by both branches.',
           'Public schema/region metadata may be read; product input tables resolve to connection-local TEMP tables. No public DML or durable audit tables.',
           'Compatibility inputs preserve existing values and memberships; no new product permission or real next-month acceptance.']}
    write_json_atomic(LAB/'cheongju_supply_http_sql_replay.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('implementation_sha256','temporary_isolation')},ensure_ascii=True))


if __name__=='__main__':main()
