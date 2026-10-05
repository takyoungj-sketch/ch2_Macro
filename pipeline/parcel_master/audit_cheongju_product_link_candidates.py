"""Local read-only product-key/co-address candidates. Never certifies matching."""
import csv
import gzip
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import text
from ledger_consumer_input_preview import ROOT, OUT, LAB, readonly
sys.path.insert(0,str(ROOT/'pipeline'))
from built.db_utils import get_built_engine
from collective.db_utils import get_collective_engine

DISTRICTS = ('43111','43112','43113','43114')


def address_pnu(bjd, lot):
    bjd = str(bjd or '').strip(); lot = re.sub(r'\s+','',str(lot or ''))
    if not re.fullmatch(r'4311[1-4][0-9]{5}',bjd): return None
    match = re.fullmatch(r'(산)?([0-9]{1,4})(?:-([0-9]{1,4}))?',lot)
    if not match: return None
    return bjd+('2' if match[1] else '1')+match[2].zfill(4)+(match[3] or '0').zfill(4)


def recovered_pnu(value, tx_bjd):
    parts = str(value or '').strip().split('|')
    if len(parts)!=2 or parts[0]!=str(tx_bjd or '').strip(): return None
    return address_pnu(*parts)


def read(factory, statement):
    engine=factory()
    try:
        if engine.url.host not in ('localhost','127.0.0.1','::1'): raise RuntimeError('Local database required')
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text("SET LOCAL statement_timeout='60s'"))
            return [dict(r._mapping) for r in conn.execute(text(statement),{'districts':list(DISTRICTS)})]
    finally:
        engine.dispose()


def candidate_context(pnu,index,statuses):
    candidates=index.get(pnu,[]) if pnu else []
    blocked=[r for r in candidates if statuses.get(r['mgmt_pk']) not in (None,'canonical_address')]
    eligible=[r for r in candidates if r not in blocked]
    outcome = 'no_latest_title_candidate' if not candidates else 'identity_blocked_only' if not eligible else 'single_title_candidate' if len(eligible)==1 else 'multiple_title_candidates'
    return {'candidate_status':outcome,'eligible_title_candidate_pks':[r['mgmt_pk'] for r in eligible],
            'blocked_title_candidate_pks':[r['mgmt_pk'] for r in blocked],
            'source_verified_candidate_count':sum(statuses.get(r['mgmt_pk'])=='canonical_address' for r in eligible),
            'processed_only_candidate_count':sum(r['mgmt_pk'] not in statuses for r in eligible),
            'candidate_ledger_kind_counts':dict(Counter(r['ledger_kind'] for r in eligible)),
            'independent_match_verification':'unverified','new_assignment':'none'}


def summarize(rows,key_fields):
    return {'rows':len(rows),'unique_product_keys':len({tuple(str(r[k]) for k in key_fields) for r in rows}),
            'candidate_statuses':dict(Counter(r['candidate_status'] for r in rows)),
            'flag_counts':dict(Counter(flag for r in rows for flag in r['flags'])),
            'rows_touching_source_verified_candidates':sum(r['source_verified_candidate_count']>0 for r in rows),
            'rows_with_processed_only_candidates':sum(r['processed_only_candidate_count']>0 for r in rows)}


def main():
    coverage=json.loads((LAB/'cheongju_building_trait_coverage.json').read_text(encoding='utf-8'))
    pair=next(r for r in coverage['pairs'] if r['building_snapshot']=='2026-07')
    path=OUT/'building_identity_2026-07.csv.gz'; source_sha=hashlib.sha256(path.read_bytes()).hexdigest()
    if source_sha!=pair['input_sha256']['buildings']: raise ValueError('Frozen city title index changed')
    index=defaultdict(list)
    with gzip.open(path,'rt',encoding='utf-8',newline='') as stream:
        for r in csv.DictReader(stream): index[r['pnu']].append(r)
    v2=readonly(OUT/'building_source_staging_v2_full.sqlite')
    statuses=dict(v2.execute("SELECT pk,identity_status FROM title_observation WHERE snapshot='2026-07'")); v2.close()
    built=read(get_built_engine,"""SELECT t.transaction_hash,t.asset_type,t.beopjungri_code,t.lot_number,
      t.is_partial_ownership,t.contract_date,e.recovered_lot,e.bldrgst_pk,e.match_tier,e.snapshots_matched
      FROM built_transactions t LEFT JOIN built_transaction_enrichment e USING(transaction_hash)
      WHERE t.sigungu_code IN (SELECT unnest(CAST(:districts AS text[])))""")
    collective=read(get_collective_engine,"""WITH ranked AS (
      SELECT building_key,asset_type,beopjungri_code,lot_number,as_of_month,window_years,
      ROW_NUMBER() OVER(PARTITION BY building_key,asset_type ORDER BY as_of_month DESC,window_years DESC) rn
      FROM collective_building_stats WHERE asset_type IN ('apartment','officetel','rowhouse'))
      SELECT r.building_key,r.asset_type,r.beopjungri_code,r.lot_number,r.as_of_month,r.window_years,
      lp.representative_pnu,lp.assessed_land_price_year,lp.source AS price_source
      FROM ranked r LEFT JOIN collective_building_assessed_land_price lp
      ON lp.building_key=r.building_key AND lp.asset_type=r.asset_type
      WHERE r.rn=1 AND substring(r.beopjungri_code,1,5) IN (SELECT unnest(CAST(:districts AS text[])))""")
    built_reviews=[]; collective_reviews=[]
    for row in built:
        pnu=recovered_pnu(row['recovered_lot'],row['beopjungri_code']); flags=[]
        context=candidate_context(pnu,index,statuses)
        if not row['recovered_lot']: context['candidate_status']='no_existing_recovered_address'
        elif not pnu: context['candidate_status']='invalid_or_conflicting_recovered_address'; flags.append('recovered_address_identity_conflict')
        exact=address_pnu(row['beopjungri_code'],row['lot_number'])
        if exact and pnu and exact!=pnu: flags.append('original_exact_address_differs')
        # Legacy recovered key omits land type. Keep mountain counterpart evidence separate.
        if pnu and pnu[10]=='1' and index.get(pnu[:10]+'2'+pnu[11:]): flags.append('mountain_counterpart_in_latest_title_index')
        if row['is_partial_ownership']: flags.append('partial_ownership_do_not_assign_whole_site')
        if row['bldrgst_pk'] and str(row['bldrgst_pk']).strip() not in context['eligible_title_candidate_pks']:
            flags.append('existing_building_pk_not_in_latest_address_candidates')
        if context['blocked_title_candidate_pks']: flags.append('source_identity_blocked_candidate')
        built_reviews.append({**row,'derived_address_pnu':pnu,'flags':flags,**context,
                              'temporal_policy':'latest_title_coaddress_audit_not_historical_assignment'})
    for row in collective:
        address=address_pnu(row['beopjungri_code'],row['lot_number']); mart=str(row['representative_pnu'] or '').strip() or None
        flags=[]
        if mart and not re.fullmatch(r'4311[1-4][0-9]{5}[12][0-9]{8}',mart): flags.append('invalid_existing_mart_pnu'); mart=None
        if mart and address and mart!=address: flags.append('mart_pnu_differs_from_latest_stats_address')
        if not address: flags.append('latest_stats_address_not_strictly_parseable')
        if not mart: flags.append('no_existing_price_mart_pnu')
        context=candidate_context(mart or address,index,statuses)
        address_context=candidate_context(address,index,statuses)
        if context['blocked_title_candidate_pks']: flags.append('source_identity_blocked_candidate')
        differences=[name for name,a,b in (('bjd',0,10),('land_type',10,11),('main_lot',11,15),('sub_lot',15,19)) if mart and address and mart[a:b]!=address[a:b]]
        collective_reviews.append({**row,'strict_latest_stats_pnu':address,'lookup_pnu':mart or address,'flags':flags,**context,
                                   'latest_stats_address_candidates':address_context,'pnu_difference_components':differences})
    report={'run_date':date.today().isoformat(),'title_index_snapshot':'2026-07','title_index_rows':sum(map(len,index.values())),
            'title_index_sha256':source_sha,'source_verified_title_observations':len(statuses),
            'built':summarize(built_reviews,('transaction_hash',)),
            'collective_residential':summarize(collective_reviews,('building_key','asset_type')),
            'collective_pnu_conflict_breakdown':{'by_asset_type':dict(Counter(r['asset_type'] for r in collective_reviews if r['pnu_difference_components'])),
                                               'by_component':dict(Counter(c for r in collective_reviews for c in r['pnu_difference_components']))},
            'checks':{'built_keys_unique':len({r['transaction_hash'] for r in built_reviews})==len(built_reviews),
                      'collective_keys_unique':len({(r['building_key'],r['asset_type']) for r in collective_reviews})==len(collective_reviews),
                      'no_assignment_or_verification_promotion':all(r['new_assignment']=='none' and r['independent_match_verification']=='unverified' for r in built_reviews+collective_reviews)},
            'limitations':['Co-address title candidates do not certify a transaction or danji match.',
                           'Built cohort includes all locally stored city transactions, not an active/valid regression sample.',
                           'City title index is a frozen processed extract; only 4,000-PK cohort observations have source-v2 review.',
                           'Latest title co-address audit is not transaction-time matching or preservation of historical candidates.',
                           'Residential collective only: commercial road clusters have no one-to-one danji address contract in this audit.',
                           'Separate local read-only database snapshots; not a synchronized production audit.']}
    if not all(report['checks'].values()): raise AssertionError('Duplicate product keys or assignment promotion')
    with gzip.open(OUT/'product_link_candidate_review.json.gz','wt',encoding='utf-8') as stream:
        json.dump({'built':built_reviews,'collective_residential':collective_reviews},stream,ensure_ascii=False,default=str)
    (LAB/'cheongju_product_link_candidates.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('Audit failed:',type(exc).__name__,flush=True)
        sys.exit(1)
