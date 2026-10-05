"""Rebuild fixed-scope price marts and replay real API response helpers offline."""
import copy
import json
import sys
import re
from collections import Counter,defaultdict
from datetime import date
from time import perf_counter

from ledger_consumer_input_preview import ROOT,OUT,LAB
from ledger_supply_bundle import load_verified_supply,verify_manifest,FrozenListLookup,sha
from ledger_supply_artifacts import write_gzip_atomic,write_json_atomic
from integrated_ledger_v2 import digest
from cheongju_numeric_supply_shadow import equal_value

sys.path.insert(0,str(ROOT/'pipeline'));sys.path.insert(0,str(ROOT/'backend'))
from build_collective_building_stats import _records_from_row as residential_record
from build_collective_commercial_cluster_stats import _record_from_row as commercial_record
from parcel_master.paths import bldrgst_dir,TITLE_COLS
from app.collective.building_stats_query import _stats_row_from_parts
from app.collective.analysis_gates import count_recent_transactions,evaluate_analysis_gates
from app.collective.schemas import AnalysisFeatures
from app.collective.danji_attributes import attach_danji_list_fields
from app.collective_commercial.cluster_stats_query import _cluster_row_from_parts
from app.built.router import _serialize_tx_row
from app.built.schemas import BuiltTransactionRow
from app.built.enrichment_join import canonical_zone_label

PRICE_FIELDS=('count','mean','std','ci_lower','ci_upper','p_min','p25','median','p75','p_max')


def local_title_inventory():
    found=[]
    for folder in bldrgst_dir().iterdir():
        match=re.fullmatch(r'국토교통부_건축물대장_표제부\+\((\d{4})년\+(\d{2})월\)',folder.name)
        if not match:continue
        path=folder/'mart_djy_03.txt'
        if path.is_file():found.append({'snapshot':match[1]+'-'+match[2],'bytes':path.stat().st_size})
    found.sort(key=lambda r:r['snapshot'])
    return {'original_title_files':found,'after_frozen_2026_07':[r['snapshot'] for r in found if r['snapshot']>'2026-07'],
            'scope':'Local original title folders only; availability is not schema/hash/authority validation.',
            'product_field_columns':len(TITLE_COLS)}


def rebuild(stats,transactions,key,builder):
    groups=defaultdict(list)
    for row in transactions:groups[(row[key],row['asset_type'])].append(row)
    if set(groups)!={(row[key],row['asset_type']) for row in stats}:raise ValueError('Frozen mart/transaction key scope differs')
    records=[];diffs=[]
    for old in stats:
        scope=groups[(old[key],old['asset_type'])]
        start,end=old['period_start'],old['period_end']
        if any(not r['is_valid'] or float(r['unit_price'])<=0 or not start<=r['contract_date']<=end for r in scope):
            raise ValueError('Frozen transaction violates mart window')
        # Metadata remains frozen: this audit recomputes price statistics, not SQL MAX metadata joins.
        row={**old,'prices':sorted(float(r['unit_price']) for r in scope)}
        rec=builder(row,as_of_month=date.fromisoformat(old['as_of_month']),window_years=old['window_years'],
                    period_start=date.fromisoformat(start),period_end=date.fromisoformat(end),batch_id='frozen-ledger-price-replay-v1')
        differences=[field for field in PRICE_FIELDS if not equal_value(old[field],rec[field])]
        if differences:diffs.append({'key':old[key],'asset_type':old['asset_type'],'fields':differences,
                                    'stored':{f:old[f] for f in differences},'recomputed':{f:rec[f] for f in differences}})
        records.append({**old,**{field:rec[field] for field in PRICE_FIELDS}})
    return records,groups,diffs


def residential_responses(records,groups,attributes,prices):
    items=[]
    for r in records:
        years=[t['contract_year'] for t in groups[(r['building_key'],r['asset_type'])]]
        recent=count_recent_transactions(years,contract_year_from=int(r['period_start'][:4]),contract_year_to=int(r['period_end'][:4]))
        gates=evaluate_analysis_gates(r['count'],recent)
        features=AnalysisFeatures(floor_index=gates.floor_index_eligible,regression=gates.regression_eligible,
                                  count_total=gates.count_total,count_recent=gates.count_recent,messages=gates.messages)
        items.append(_stats_row_from_parts(r,asset_type=r['asset_type'],gates=features))
    attach_danji_list_fields(FrozenListLookup(attributes,prices),items)
    # model_copy update in production bypasses validation: revalidate the final response.
    return [type(item).model_validate(item.model_dump()).model_dump(mode='json') for item in items]


def built_response(tx,enrichment,enrich):
    # Restrict to fields selected by the endpoint; frozen DB-only columns must not leak.
    selected=set(BuiltTransactionRow.model_fields)-{'structure_group','match_tier','match_rule','recovered_lot','zone_type_ledger','zone_source','building_year'}
    row={k:v for k,v in tx.items() if k in selected}
    row['transaction_hash']=tx['transaction_hash']
    if enrich:
        e=enrichment or {}
        row.update({k:e.get(k) for k in ('structure_group','match_tier','match_rule','recovered_lot')})
        zone=canonical_zone_label([tx['zone_type']]) if tx.get('zone_type') else None
        zone=zone or canonical_zone_label(e.get('zone_labels'))
        row['zone_type_filled']=zone;row['zone_type_first']=zone
    return _serialize_tx_row(row,enrich=enrich).model_dump(mode='json')


def main():
    started=perf_counter();frozen,paired,manifest_hash=load_verified_supply(ROOT)
    original_stats={(r['building_key'],r['asset_type']):r for r in frozen['collective']['residential_stats']}
    if len(paired['residential'])!=len(original_stats) or {(r['stats']['building_key'],r['stats']['asset_type']) for r in paired['residential']}!=set(original_stats):
        raise ValueError('Residential key scope changed')
    if any(r['stats']!=original_stats[(r['stats']['building_key'],r['stats']['asset_type'])] for r in paired['residential']):
        raise ValueError('Residential stats changed')
    rs,rgroup,rdiff=rebuild(frozen['collective']['residential_stats'],frozen['collective']['residential_transactions'],'building_key',residential_record)
    cs,_,cdiff=rebuild(frozen['collective']['commercial_stats'],frozen['collective']['commercial_transactions'],'cluster_key',commercial_record)
    compatible_attrs=copy.deepcopy(frozen['collective']['attributes'])
    replacements={(r['stats']['building_key'],r['stats']['asset_type'],r['compatible_attributes']['snapshot_ym']):r['compatible_attributes']
                  for r in paired['residential'] if r['compatible_attributes']}
    compatible_attrs=[replacements.get((r['building_key'],r['asset_type'],r['snapshot_ym']),r) for r in compatible_attrs]
    prices=copy.deepcopy(frozen['collective']['prices'])
    paired_by_key={(r['stats']['building_key'],r['stats']['asset_type']):r for r in paired['residential']}
    for r in prices:r['assessed_land_price']=paired_by_key[(r['building_key'],r['asset_type'])]['compatible_price']
    if paired['commercial_stats']!=frozen['collective']['commercial_stats'] or paired['commercial_transactions']!=frozen['collective']['commercial_transactions']:
        raise ValueError('Commercial frozen input changed')
    old_tx={r['transaction']['transaction_hash']:r for r in frozen['built']['transactions']}
    if len(old_tx)!=len(paired['built']) or {r['transaction']['transaction_hash'] for r in paired['built']}!=set(old_tx):raise ValueError('Built scope changed')
    for row in paired['built']:
        if row['transaction']!=old_tx[row['transaction']['transaction_hash']]['transaction']:raise ValueError('Built transaction changed')
    legacy=residential_responses(rs,rgroup,frozen['collective']['attributes'],frozen['collective']['prices'])
    supplied=residential_responses(rs,rgroup,compatible_attrs,prices)
    commercial=[_cluster_row_from_parts(r).model_dump(mode='json') for r in cs]
    built={}
    for enrich in (False,True):
        key='enriched' if enrich else 'ledger'
        left=[];right=[]
        for row in paired['built']:
            old=old_tx[row['transaction']['transaction_hash']]
            left.append(built_response(old['transaction'],old['enrichment'],enrich))
            right.append(built_response(row['transaction'],row['compatible_enrichment'],enrich))
        built[key]={'legacy':left,'compatible':right}
    checks={'residential_responses_equal':legacy==supplied,'commercial_306_responses_valid':len(commercial)==306,
            'built_ledger_responses_equal':built['ledger']['legacy']==built['ledger']['compatible'],
            'built_enriched_responses_equal':built['enriched']['legacy']==built['enriched']['compatible'],
            'residential_counts_match_stored':all('count' not in r['fields'] for r in rdiff),
            'commercial_counts_match_stored':all('count' not in r['fields'] for r in cdiff),
            'residential_all_price_fields_match_stored':not rdiff,
            'commercial_all_price_fields_match_stored':not cdiff,
            'no_product_permission_escalation':all(r[name]['permissions'][flag] is False for r in paired['residential']
                 for name in ('title_candidate','retained_attributes','effective_attributes')
                 for flag in ('product_enrichment','quantity_aggregation','regression')) and all(
                    r['candidate_comparisons']['permissions'][flag] is False for r in paired['built']
                    for flag in ('product_enrichment','quantity_aggregation','regression'))}
    if not all(checks.values()):raise AssertionError(checks)
    # A refresh may have replaced intermediate reports while this consumer was running.
    if verify_manifest(ROOT)[1]!=manifest_hash:raise ValueError('Supply generation changed during replay')
    payload={'supply_manifest_sha256':manifest_hash,'residential_price_mart':rs,'commercial_price_mart':cs,
             'stored_price_mart_differences':{'residential':rdiff,'commercial':cdiff},
             'residential_responses':{'legacy':legacy,'compatible':supplied},'commercial_responses':commercial,'built_responses':built}
    path=OUT/'product_marts_api_replay.json.gz';write_gzip_atomic(path,payload)
    report={'audit':'fixed-price-mart-and-api-helper-replay-v1','supply_manifest_sha256':manifest_hash,
            'local_title_inventory':local_title_inventory(),
            'counts':{'residential_marts':len(rs),'residential_transactions':sum(map(len,rgroup.values())),
                      'commercial_marts':len(cs),'commercial_transactions':len(frozen['collective']['commercial_transactions']),
                      'built_transactions_per_mode':len(paired['built'])},
            'stored_mart_difference_counts':{'residential':len(rdiff),'commercial':len(cdiff)},
            'stored_mart_difference_fields':{name:dict(Counter(f for r in rows for f in r['fields'])) for name,rows in [('residential',rdiff),('commercial',cdiff)]},
            'checks':checks,'payload_content_sha256':digest(payload),'gzip_sha256':sha(path),'production_apply':False,
            'elapsed_seconds':perf_counter()-started,
            'implementation_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in (
                ROOT/'pipeline/build_collective_building_stats.py',ROOT/'pipeline/build_collective_commercial_cluster_stats.py',ROOT/'pipeline/stats.py',
                ROOT/'backend/app/collective/building_stats_query.py',ROOT/'backend/app/collective/danji_attributes.py',ROOT/'backend/app/collective/analysis_gates.py',
                ROOT/'backend/app/collective/schemas.py',ROOT/'backend/app/collective_commercial/cluster_stats_query.py',ROOT/'backend/app/collective_commercial/schemas.py',
                ROOT/'backend/app/built/router.py',ROOT/'backend/app/built/schemas.py',ROOT/'backend/app/built/enrichment_join.py',
                ROOT/'pipeline/parcel_master/ledger_supply_bundle.py',ROOT/'pipeline/parcel_master/replay_cheongju_supply_marts_api.py')},
            'limitations':['Offline actual response helpers and Pydantic validation, not HTTP routing/auth/pagination or PostgreSQL SQL execution.',
                           'Recomputed rolling price fields only; frozen address/cluster metadata retained, annual/other windows excluded.',
                           'Residential attribute lookup latest snapshot is scoped to frozen rows, not a fresh whole-table global lookup.',
                           'Analysis gates use frozen window transaction years, not a live annual table query.',
                           'Fixed historical inputs; next-month availability is recorded separately and is not an update acceptance test.']}
    write_json_atomic(LAB/'cheongju_supply_marts_api_replay.json',report)
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
