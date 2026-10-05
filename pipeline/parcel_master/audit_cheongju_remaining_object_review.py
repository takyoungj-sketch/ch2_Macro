"""Read-only remaining queue and two title histories. No object reassignment."""
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import bindparam, text
from audit_cheongju_apartment_site_review import scan_titles, shadow_gate
from audit_cheongju_address_pair_impact import canonical_hash
from audit_cheongju_product_link_candidates import address_pnu
from audit_cheongju_named_object_mix import get_collective_engine
from ledger_consumer_input_preview import ROOT, OUT, LAB
from parcel_master.paths import title_path, kapt_info_xlsx, kapt_pnu_xlsx


def review_category(row, sites):
    if any(s['address_identity'][0]!='pnu' for s in sites):
        category='development_block_identity_unresolved'
    elif row['distinct_legal_dongs']>1:
        category='cross_legal_dong_observed_addresses_membership_review'
    elif row['decision']['distinct_kapt_codes']>1:
        category='shared_parcel_multiple_management_codes_no_auto_split'
    else:
        category='source_membership_review'
    return {'category':category,'new_object_key':None,'new_representative_pnu':None,
            'production_apply':False,'membership_status':'unverified'}


def code_context(info):
    codes={r['단지코드'].strip() for r in info if r['단지코드'].strip()}
    approvals=defaultdict(set)
    for r in info:
        if r['단지코드'].strip() and r['사용승인일'].strip(): approvals[r['단지코드'].strip()].add(r['사용승인일'].strip())
    shared=set.intersection(*(approvals[c] for c in sorted(codes))) if codes else set()
    return {'distinct_codes':len(codes),'common_approval_dates_across_codes':sorted(shared),
            'code_change_history_verified':False,'alias_certified':False,'auto_split':False,'auto_merge':False}


def main():
    paths=[OUT/'named_object_mix_review_queue.json.gz',OUT/'apartment_site_review_evidence.json.gz']
    protected={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with gzip.open(paths[0],'rt',encoding='utf-8') as f: queue=json.load(f)
    with gzip.open(paths[1],'rt',encoding='utf-8') as f: prior=json.load(f)
    done={c['building_key'] for c in prior}
    remaining=sorted([r for r in queue if r['building_key'] not in done],key=lambda r:(r['asset_type'],r['building_key']))
    if len(remaining)!=35 or len(queue)!=52 or len(done)!=17: raise ValueError('Queue cohort changed')
    missing=[s for c in prior for s in c['sites'] if not s['kapt_codes']]
    if len(missing)!=2: raise ValueError('Unresolved prior addresses changed')
    historic_pnus={s['pnu'] for s in missing}
    pnus={p for r in remaining for p in r['observed_pnus']} | historic_pnus
    source_inventory=json.loads((LAB/'cheongju_named_object_mix.json').read_text(encoding='utf-8'))['source_inventory']
    for name,path in [('kapt_representative',kapt_pnu_xlsx()),('kapt_basic_info',kapt_info_xlsx())]:
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source_inventory[name]['sha256']: raise ValueError('K-apt source changed')
    ids=[r['stats_id'] for r in remaining]
    sql='''SELECT s.id stats_id,t.beopjungri_code,t.lot_number,to_char(t.contract_date,'YYYY-MM') contract_month,count(*) transactions
      FROM collective_building_stats s JOIN collective_transactions t USING(building_key,asset_type)
      WHERE s.id IN :ids AND t.is_valid=true AND t.unit_price>0 AND t.contract_date BETWEEN s.period_start AND s.period_end
      GROUP BY s.id,t.beopjungri_code,t.lot_number,to_char(t.contract_date,'YYYY-MM')
      ORDER BY s.id,t.beopjungri_code,t.lot_number,contract_month'''
    engine=get_collective_engine()
    try:
        if engine.url.host not in ('localhost','127.0.0.1','::1'): raise RuntimeError('Local DB required')
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY')); conn.execute(text("SET LOCAL statement_timeout='60s'")); conn.execute(text('SET LOCAL enable_mergejoin=off'))
            months=[dict(r._mapping) for r in conn.execute(text(sql).bindparams(bindparam('ids',expanding=True)),{'ids':ids})]
            snap=dict(conn.execute(text('SELECT current_database() db,current_timestamp observed_at,txid_current_snapshot() snapshot')).one()._mapping)
    finally: engine.dispose()
    by_id=defaultdict(list)
    for m in months: by_id[m['stats_id']].append(m)
    expected=json.loads((LAB/'cheongju_relation_source_evidence.json').read_text(encoding='utf-8'))['raw_inventory']
    sources={}; title_batches={}
    for snapshot in ('2024-09','2025-07','2026-07'):
        targets=pnus if snapshot=='2026-07' else historic_pnus
        print('Scanning title snapshot',snapshot,'target PNUs',len(targets),flush=True)
        title_batches[snapshot],sources[snapshot]=scan_titles(title_path(snapshot),targets)
        e=next(r for r in expected if r.get('snapshot')==snapshot and r['source']=='title')
        if sources[snapshot]['sha256']!=e['sha256'] or sources[snapshot]['rows']!=e['rows']: raise ValueError('Frozen title source changed')
        pk=[t['mgmt_pk'] for ts in title_batches[snapshot].values() for t in ts]
        if len(pk)!=len(set(pk)): raise ValueError('Duplicate raw management PK')
    cases=[]
    for i,r in enumerate(remaining,1):
        observed=by_id[r['stats_id']]
        if sum(m['transactions'] for m in observed)!=r['transaction_count']: raise ValueError('Frozen transaction count changed')
        current={address_pnu(m['beopjungri_code'],m['lot_number']) for m in observed};current.discard(None)
        if current!=set(r['observed_pnus']): raise ValueError('Frozen PNU scope changed')
        sites=[]
        for p in r['address_review_partitions']:
            identity=p['address_identity'];pnu=identity[1] if identity[0]=='pnu' else None
            rows=[m for m in observed if (address_pnu(m['beopjungri_code'],m['lot_number'])==pnu if pnu else
                 [str(m['beopjungri_code'] or '').strip(),str(m['lot_number'] or '').strip()]==identity[1:])]
            if sum(m['transactions'] for m in rows)!=p['transactions']: raise ValueError('Address partition drift')
            raw=title_batches['2026-07'].get(pnu,[]) if pnu else []
            codes={k['danji_code'] for k in r['raw_kapt_representative_rows'] if k['pnu']==pnu and k['danji_code']}
            info=[k for k in r['raw_kapt_basic_info'] if k['단지코드'].strip() in codes]
            sites.append({'address_identity':identity,'transactions':p['transactions'],'observed_addresses':p['address_groups'],
                'monthly_observations':rows,'raw_titles':raw,'raw_kapt_basic_info':info,
                'code_context':code_context(info),'title_status':'address_not_canonical' if not pnu else 'titles_present' if raw else 'no_titles_in_latest_snapshot',
                'title_purposes':dict(Counter(t['main_purpose'] for t in raw)),
                'title_approval_dates':sorted({t['approval_date'].strip() for t in raw if t['approval_date'].strip()}),
                'title_names':sorted({t['building_name'].strip() for t in raw if t['building_name'].strip()})})
        cases.append({'case_id':f'remaining-{i:02d}','building_key':r['building_key'],'asset_type':r['asset_type'],'district':r['district'],
            'transaction_count':r['transaction_count'],'as_of_month':r['as_of_month'],'sites':sites,'decision':review_category(r,sites),
            'baseline_price_mart':r['baseline_price_mart'],'baseline_attribute_rows':r['existing_attribute_rows'],
            'shadow_gate':shadow_gate(r['address_review_partitions'])})
    history=[]
    for s in missing:
        batches=[]
        for snapshot in title_batches:
            raw=title_batches[snapshot].get(s['pnu'],[])
            batches.append({'snapshot':snapshot,'raw_titles':raw,'title_count':len(raw),
                'purposes':dict(Counter((t['main_purpose']+' / '+t['purpose_detail']) for t in raw)),
                'mgmt_pks':sorted(t['mgmt_pk'] for t in raw)})
        common=set.intersection(*(set(b['mgmt_pks']) for b in batches))
        history.append({'pnu':s['pnu'],'observed_addresses':s['observed_addresses'],'batches':batches,
                        'management_pks_seen_at_same_address_in_all_snapshots':sorted(common),
                        'assessment':'stable_title_address_observations_membership_unverified' if common else 'historical_address_review_required',
                        'new_object_key':None,'production_apply':False})
    checks={'remaining_cohort_35_preserved':len(cases)==35,'previous_two_addresses_preserved':len(history)==2,
        'all_transaction_counts_conserved':sum(c['transaction_count'] for c in cases)==3726,
        'address_partitions_preserved':sum(len(c['sites']) for c in cases)==67,
        'protected_evidence_unchanged':all(hashlib.sha256(p.read_bytes()).hexdigest()==protected[p.name] for p in paths),
        'no_product_assignment':all(c['decision']['new_object_key'] is None and c['decision']['new_representative_pnu'] is None and not c['decision']['production_apply'] for c in cases)}
    if not all(checks.values()): raise AssertionError(checks)
    brief=[{'case_id':c['case_id'],'asset_type':c['asset_type'],'category':c['decision']['category'],'transactions':c['transaction_count'],
            'sites':[{'observed_labels':sorted({' '.join(str(g[k] or '') for k in ('addr4','lot_number','building_name')) for g in s['observed_addresses']}),
                      'transactions':s['transactions'],'title_rows':len(s['raw_titles']),'title_status':s['title_status'],
                      'title_purposes':s['title_purposes'],'title_names':s['title_names'],'kapt_names':sorted({k['단지명'] for k in s['raw_kapt_basic_info']}),
                      'code_context':s['code_context']} for s in c['sites']]} for c in cases]
    report={'audit_version':'cheongju-remaining-object-review-v1','run_date':date.today().isoformat(),'keys':len(cases),
        'transactions':sum(c['transaction_count'] for c in cases),'address_partitions':sum(len(c['sites']) for c in cases),
        'categories':dict(Counter(c['decision']['category'] for c in cases)),
        'title_statuses':dict(Counter(s['title_status'] for c in cases for s in c['sites'])),
        'shared_parcel_distinct_pnus':len({s['address_identity'][1] for c in cases if c['decision']['category']=='shared_parcel_multiple_management_codes_no_auto_split' for s in c['sites']}),
        'cases':brief,'previous_two_address_history':[{'observed_labels':sorted({' '.join(str(g[k] or '') for k in ('addr4','lot_number')) for g in h['observed_addresses']}),
             'snapshots':[{'snapshot':b['snapshot'],'title_count':b['title_count'],'purposes':b['purposes']} for b in h['batches']],
             'stable_management_pks':len(h['management_pks_seen_at_same_address_in_all_snapshots']),'assessment':h['assessment']} for h in history],
        'checks':checks,'source_inventory':{'titles':sources,'kapt':source_inventory},
        'provenance':{'protected_inputs_sha256':protected,'query_sql_sha256':canonical_hash(sql),'query_output_sha256':canonical_hash(months),
                      'database_snapshot':snap,'evidence_content_sha256':canonical_hash([cases,history]),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        'limitations':['Title absence is snapshot/source coverage, not evidence of nonexistence.',
                       'Shared PNU with multiple management codes requires object-level evidence; neither auto split nor alias merge is justified.',
                       'Same approval dates do not certify alias codes or equal physical objects.',
                       'BL development blocks remain raw observations; no PNU is invented.',
                       'Repeated management PK at a title address does not certify transaction membership or an administrative code history.',
                       'No product prices, attributes, keys, statistics or regression inputs changed.']}
    with gzip.open(OUT/'remaining_object_review_evidence.json.gz','wt',encoding='utf-8') as f: json.dump({'cases':cases,'previous_two_address_history':history},f,ensure_ascii=False)
    (LAB/'cheongju_remaining_object_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','source_inventory','provenance','limitations')},ensure_ascii=True),flush=True)


if __name__=='__main__':main()
