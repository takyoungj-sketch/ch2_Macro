"""Local city-wide named-object review. Shadow partitions are not new objects."""
import gzip
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import bindparam, text

from audit_cheongju_address_pair_impact import canonical_hash
from audit_cheongju_product_link_candidates import address_pnu
from audit_cheongju_priority_price_mart import scan_kapt
from ledger_consumer_input_preview import ROOT, OUT, LAB

sys.path.insert(0,str(ROOT/'pipeline'))
from collective.db_utils import get_collective_engine
from collective.building_keys import attach_building_identity
from parcel_master.paths import kapt_pnu_xlsx, kapt_info_xlsx


def classify(named, legal_codes, pnus, pnu_codes):
    """Mutually exclusive evidence classes; no membership certification."""
    codes = set().union(*(pnu_codes.get(p,set()) for p in pnus)) if pnus else set()
    common = set.intersection(*(set(pnu_codes.get(p,set())) for p in pnus)) if pnus else set()
    if not named:
        category = 'unnamed_key_separate_address_identity'
    elif len(legal_codes)>1:
        category = ('cross_legal_dong_multiple_kapt_codes_review' if len(codes)>1 else
                    'cross_legal_dong_single_kapt_code_membership_unverified' if codes else
                    'cross_legal_dong_no_kapt_evidence')
    elif len(pnus)>1:
        category = ('same_legal_dong_multiple_kapt_codes_review' if len(codes)>1 else
                    'same_legal_dong_shared_kapt_code_multi_parcel_unverified' if common else
                    'same_legal_dong_single_kapt_code_partial_coverage_unverified' if codes else
                    'same_legal_dong_multiple_parcels_no_kapt_evidence')
    else:
        category = 'single_or_unparseable_address_not_independently_verified'
    return {'evidence_class':category,'distinct_kapt_codes':len(codes),
            'kapt_codes':sorted(codes),'common_kapt_codes_across_all_observed_pnus':sorted(common),
            'pnus_with_kapt_representative_mapping':sum(bool(pnu_codes.get(p)) for p in pnus),
            'independent_membership_verification':'unverified','new_object_key':None,
            'new_representative_pnu':None,'production_apply':False}


def shadow_partitions(groups):
    """Keep every transaction in an address observation bucket, including invalid addresses."""
    buckets = defaultdict(list)
    for g in groups:
        pnu = address_pnu(g['beopjungri_code'],g['lot_number'])
        identity = ('pnu',pnu) if pnu else ('raw',str(g['beopjungri_code'] or '').strip(),str(g['lot_number'] or '').strip())
        buckets[identity].append(g)
    result = []
    for identity, observations in sorted(buckets.items()):
        result.append({'address_identity':list(identity),'transactions':sum(g['transactions'] for g in observations),
                       'address_groups':observations,'membership_status':'unverified','new_object_key':None})
    return result


def key_replay_flags(groups):
    flags = [False] * len(groups)
    for asset in sorted({g['asset_type'] for g in groups}):
        indices = [i for i,g in enumerate(groups) if g['asset_type']==asset]
        source_rows = [groups[i] for i in indices]
        calculated = attach_building_identity(pd.DataFrame(source_rows),asset)['building_key'].tolist()
        for i,k in zip(indices,calculated):
            flags[i] = k==groups[i]['building_key']
    return flags


def summarize(rows):
    named = [r for r in rows if r['named_key']]
    mixed = [r for r in named if r['distinct_legal_dongs']>1]
    return {'keys':len(rows),'named_keys':len(named),'unnamed_keys':len(rows)-len(named),
            'named_cross_legal_dong_keys':len(mixed),
            'transactions_in_named_cross_legal_dong_keys':sum(r['transaction_count'] for r in mixed),
            'named_same_legal_dong_multi_pnu_keys':sum(r['distinct_legal_dongs']==1 and r['distinct_observed_pnus']>1 for r in named),
            'multiple_kapt_code_keys':sum(r['decision']['distinct_kapt_codes']>1 for r in named),
            'named_cross_legal_dong_with_price_mart':sum(r['price_mart_present'] for r in mixed),
            'named_cross_legal_dong_with_building_attributes':sum(bool(r['existing_attribute_tiers']) for r in mixed),
            'unobserved_stats_address_keys':sum(r['stored_stats_address_observed'] is False for r in rows),
            'classes':dict(Counter(r['decision']['evidence_class'] for r in rows))}


def main():
    input_path = OUT/'address_pair_impact_evidence.json.gz'
    prior_path = OUT/'priority_price_mart_source_evidence.json.gz'
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (input_path,prior_path)}
    with gzip.open(input_path,'rt',encoding='utf-8') as stream:
        frozen = json.load(stream)
    selected = [r for r in frozen['residential'] if r['window_years']==7]
    commercial = [r for r in frozen['commercial'] if r['window_years']==7]
    if len(selected)!=1471 or len(commercial)!=306:
        raise AssertionError('Frozen city scope changed')
    ids = sorted(r['id'] for r in selected)
    keys = sorted({r['product_key'] for r in selected})
    sql = '''SELECT s.id stats_id,t.building_key,t.asset_type,t.beopjungri_code,t.lot_number,t.building_name,
      t.addr1,t.addr2,t.addr3,t.addr4,t.road_name,count(*) transactions,
      min(t.contract_date) first_contract,max(t.contract_date) last_contract
      FROM collective_building_stats s JOIN collective_transactions t USING(building_key,asset_type)
      WHERE s.id IN :ids AND t.is_valid=true AND t.unit_price>0 AND t.contract_date BETWEEN s.period_start AND s.period_end
      GROUP BY s.id,t.building_key,t.asset_type,t.beopjungri_code,t.lot_number,t.building_name,
        t.addr1,t.addr2,t.addr3,t.addr4,t.road_name
      ORDER BY s.id,t.beopjungri_code,t.lot_number,t.building_name,t.addr1,t.addr2,t.addr3,t.addr4,t.road_name'''
    engine = get_collective_engine()
    try:
        if engine.url.host not in ('localhost','127.0.0.1','::1'):
            raise RuntimeError('Local database required')
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text("SET LOCAL statement_timeout='60s'"))
            conn.execute(text('SET LOCAL enable_mergejoin=off'))
            groups = [dict(r._mapping) for r in conn.execute(text(sql).bindparams(bindparam('ids',expanding=True)),{'ids':ids})]
            attrs = [dict(r._mapping) for r in conn.execute(text('SELECT building_key,asset_type,snapshot_ym,match_tier,match_rule,danji_code,match_danji_codes FROM collective_building_attributes WHERE building_key IN :keys ORDER BY building_key,asset_type,snapshot_ym').bindparams(bindparam('keys',expanding=True)),{'keys':keys})]
            mart = [dict(r._mapping) for r in conn.execute(text('SELECT * FROM collective_building_assessed_land_price WHERE building_key IN :keys ORDER BY building_key,asset_type').bindparams(bindparam('keys',expanding=True)),{'keys':keys})]
            snapshot = dict(conn.execute(text('SELECT current_database() db,current_timestamp observed_at,txid_current_snapshot() snapshot')).one()._mapping)
    finally:
        engine.dispose()
    print('City transaction address/name groups',len(groups),flush=True)
    # Presale is the only name-normalizing asset. Other assets must replay their
    # own identity function, rather than inherit presale brand alias rules.
    # Associate flags with original dictionaries; DataFrame None->NaN conversion
    # must not change the identity of nullable address-group dictionary keys.
    replayed = {id(g):flag for g,flag in zip(groups,key_replay_flags(groups))}
    pnus = {address_pnu(g['beopjungri_code'],g['lot_number']) for g in groups}; pnus.discard(None)
    raw_kapt,kmeta = scan_kapt(kapt_pnu_xlsx(),pnus,set())
    pnu_codes = defaultdict(set)
    for r in raw_kapt:
        if r['danji_code']:
            pnu_codes[r['pnu']].add(r['danji_code'])
    codes = {r['danji_code'] for r in raw_kapt if r['danji_code']}
    info_path = kapt_info_xlsx()
    frame = pd.read_excel(info_path,skiprows=1,dtype=str).fillna('')
    frame.columns = [str(c).strip() for c in frame.columns]
    info = [r for r in frame.to_dict(orient='records') if str(r['단지코드']).strip() in codes]
    imeta = {'file':str(info_path.relative_to(ROOT)),'sha256':hashlib.sha256(info_path.read_bytes()).hexdigest(),
             'rows':len(frame),'selected_rows':len(info)}
    known_codes = {str(r['단지코드']).strip() for r in info}
    print('Kapt representative rows',len(raw_kapt),'basic info rows',len(info),flush=True)
    by_id = defaultdict(list)
    for g in groups:
        by_id[g['stats_id']].append(g)
    attr_index = defaultdict(list)
    for a in attrs:
        attr_index[(a['building_key'],a['asset_type'])].append(a)
    mart_index = {(r['building_key'],r['asset_type']):r for r in mart}
    rows = []
    for stats in selected:
        observed = by_id[stats['id']]
        if sum(g['transactions'] for g in observed)!=stats['eligible_transaction_count']:
            raise ValueError('Frozen transaction count changed')
        current_pnus = {address_pnu(g['beopjungri_code'],g['lot_number']) for g in observed}; current_pnus.discard(None)
        if current_pnus!=set(stats['observed_cheongju_pnus']):
            raise ValueError('Frozen address candidates changed')
        legal_codes = {str(g['beopjungri_code'] or '').strip() for g in observed
                       if re.fullmatch(r'[0-9]{10}',str(g['beopjungri_code'] or '').strip())}
        names = {str(g['building_name'] or '').strip() for g in observed}
        named = bool(names) and all(names)
        key = (stats['product_key'],stats['asset_type'])
        decision = classify(named,legal_codes,current_pnus,pnu_codes)
        row = {'building_key':key[0],'asset_type':key[1],'stats_id':stats['id'],
               'district':stats['district'],'as_of_month':stats['as_of_month'],'named_key':named,
               'transaction_count':sum(g['transactions'] for g in observed),
               'distinct_legal_dongs':len(legal_codes),'observed_legal_codes':sorted(legal_codes),
               'distinct_observed_pnus':len(current_pnus),'observed_pnus':sorted(current_pnus),
               'unparseable_address_groups':sum(address_pnu(g['beopjungri_code'],g['lot_number']) is None for g in observed),
               'existing_attribute_tiers':[a['match_tier'] for a in attr_index[key]],
               'existing_attribute_rows':attr_index[key],'price_mart_present':key in mart_index,
               'baseline_price_mart':mart_index.get(key),'stored_stats_address_observed':stats['stored_tuple_observed'],
               'existing_key_reproduced':all(replayed[id(g)] for g in observed),
               'raw_kapt_representative_rows':[r for r in raw_kapt if r['pnu'] in current_pnus],
               'raw_kapt_basic_info':[r for r in info if str(r['단지코드']).strip() in decision['kapt_codes']],
               'kapt_codes_missing_raw_basic_info':sorted(set(decision['kapt_codes'])-known_codes),
               'decision':decision,'address_review_partitions':shadow_partitions(observed)}
        rows.append(row)
    with gzip.open(prior_path,'rt',encoding='utf-8') as stream:
        priority = json.load(stream)
    row_index = {(r['building_key'],r['asset_type']):r for r in rows}
    previous_source = json.loads((LAB/'cheongju_priority_price_mart_source_review.json').read_text(encoding='utf-8'))['source_inventory']
    checks = {'one_row_per_key':len(row_index)==len(rows)==len(selected),
              'kapt_sources_match_prior_priority_review':kmeta['sha256']==previous_source['kapt']['sha256'] and imeta['sha256']==previous_source['kapt_basic_info']['sha256'],
              'all_transaction_keys_reproduced':all(r['existing_key_reproduced'] for r in rows),
              'all_partition_transaction_counts_conserved':all(sum(p['transactions'] for p in r['address_review_partitions'])==r['transaction_count'] for r in rows),
              'prior_six_mixed_keys_reproduced':all(row_index[(r['building_key'],r['asset_type'])]['distinct_legal_dongs']==r['distinct_observed_legal_dongs'] and row_index[(r['building_key'],r['asset_type'])]['decision']['distinct_kapt_codes']==len({x['danji_code'] for x in r['observed_address_kapt_raw']}) for r in priority),
              'no_new_object_or_representative_assignment':all(r['decision']['new_object_key'] is None and r['decision']['new_representative_pnu'] is None and not r['decision']['production_apply'] for r in rows),
              'prior_evidence_unchanged':all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[p.name] for p in (input_path,prior_path))}
    # A key replay discrepancy is evidence to investigate; do not hide it.
    if not all(v for k,v in checks.items() if k!='all_transaction_keys_reproduced'):
        raise AssertionError(checks)
    review = [r for r in rows if r['named_key'] and (r['distinct_legal_dongs']>1 or r['decision']['distinct_kapt_codes']>1)]
    report = {'run_date_kst':datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat(),
              'audit_version':'cheongju-named-object-mix-v1','all_residential_and_presale':summarize(rows),
              'ledger_consumer_types':summarize([r for r in rows if r['asset_type']!='presale']),
              'by_asset_type':{a:summarize([r for r in rows if r['asset_type']==a]) for a in sorted({r['asset_type'] for r in rows})},
              'by_district':{d:summarize([r for r in rows if r['district']==d]) for d in sorted({r['district'] for r in rows})},
              'review_queue_keys':len(review),'review_queue_address_partitions':sum(len(r['address_review_partitions']) for r in review),
              'review_queue_transactions':sum(r['transaction_count'] for r in review),
              'key_replay_discrepancy_keys':sum(not r['existing_key_reproduced'] for r in rows),
              'missing_kapt_basic_info_codes':sorted(codes-known_codes),
              'commercial_paired_context':{'keys':len(commercial),'address_tuple_unobserved_keys':sum(r['stored_tuple_observed'] is False for r in commercial),
                                            'analysis_unit':'road_cluster','action':'keep_existing_cluster_identity'},
              'checks':checks,'source_inventory':{'kapt_representative':kmeta,'kapt_basic_info':imeta},
              'provenance':{'protected_inputs_sha256':hashes,'database_snapshot':snapshot,
                            'query_output_sha256':canonical_hash([groups,attrs,mart]),
                            'query_sql_sha256':canonical_hash(sql),
                            'code_sha256':hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
                            'building_key_code_sha256':hashlib.sha256((ROOT/'pipeline/collective/building_keys.py').read_bytes()).hexdigest(),
                            'evidence_content_sha256':canonical_hash(rows)},
              'limitations':['Local latest-per-key longest stored window, not a production VPS or synchronized global-month audit.',
                             'Legal-code differences may include address changes; physical cause and object membership remain unverified.',
                             'K-apt representative mapping is not a full parcel set; one code on only one address does not prove a multi-parcel site.',
                             'Multiple K-apt codes can share a parcel; code counts alone do not certify separate transaction objects.',
                             'Address review partitions are diagnostic buckets, not new building keys or certified property boundaries.',
                             'Commercial paired context reuses the protected prior road-cluster audit; no residential split rule applied to commercial.',
                             'No product keys, representative prices, aggregates, or regression inputs changed.']}
    for filename,payload in (('named_object_mix_evidence.json.gz',rows),('named_object_mix_review_queue.json.gz',review)):
        with gzip.open(OUT/filename,'wt',encoding='utf-8') as stream:
            json.dump(payload,stream,ensure_ascii=False,default=str)
    (LAB/'cheongju_named_object_mix.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_inventory','provenance','limitations')},ensure_ascii=True),flush=True)


if __name__=='__main__':
    main()
