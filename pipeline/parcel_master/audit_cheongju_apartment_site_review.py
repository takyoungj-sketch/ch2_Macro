"""Evidence review of 17 mixed apartment keys; never certifies membership."""
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path

from sqlalchemy import bindparam, text
from audit_cheongju_address_pair_impact import canonical_hash
from audit_cheongju_product_link_candidates import address_pnu
from audit_cheongju_relation_source_evidence import pnu_from_fields
from ledger_consumer_input_preview import ROOT, OUT, LAB
from audit_cheongju_named_object_mix import get_collective_engine
from parcel_master.paths import title_path, kapt_pnu_xlsx, kapt_info_xlsx


def compare_sites(a, b):
    """Only supporting evidence. Temporal overlap is not code-change history."""
    ca, cb = set(a['kapt_codes']), set(b['kapt_codes'])
    shared_months = sorted(set(a['contract_months']) & set(b['contract_months']))
    signals = {
        'disjoint_nonempty_kapt_codes': bool(ca and cb and not ca & cb),
        'different_nonempty_kapt_names': bool(a['names'] and b['names'] and not set(a['names']) & set(b['names'])),
        'different_nonempty_approval_dates': bool(a['approval_dates'] and b['approval_dates'] and not set(a['approval_dates']) & set(b['approval_dates'])),
        'different_nonempty_road_addresses': bool(a['road_addresses'] and b['road_addresses'] and not set(a['road_addresses']) & set(b['road_addresses'])),
        'communal_housing_present_in_both_title_addresses': a['communal_housing_title_count'] > 0 and b['communal_housing_title_count'] > 0,
        'kapt_approval_dates_replayed_in_both_titles': bool(set(a['approval_dates']) & set(a['title_approval_dates'])) and bool(set(b['approval_dates']) & set(b['title_approval_dates'])),
        'transactions_observed_in_common_months': bool(shared_months),
    }
    return {'pnu_pair': [a['pnu'], b['pnu']], 'signals': signals,
            'common_contract_months': shared_months,
            'assessment': 'distinct_sites_supported_membership_unverified' if all(signals.values()) else 'insufficient_or_conflicting_site_evidence',
            'physical_membership_certified': False, 'code_change_history_verified': False}


def shadow_gate(partitions):
    return {'status': 'object_scope_review_hold', 'transactions': sum(p['transactions'] for p in partitions),
            'address_partitions': len(partitions), 'new_object_key': None,
            'inherited_price_mart': None, 'inherited_building_attributes': None,
            'production_apply': False,
            'reason': 'Whole mixed-key attributes and prices cannot certify each observed site.'}


def scan_titles(path, pnus):
    found = defaultdict(list); sha = hashlib.sha256(); n = 0
    with path.open('rb') as stream:
        for n, line in enumerate(stream, 1):
            sha.update(line)
            first = line.rstrip(b'\r\n').split(b'|', 13)
            pnu = pnu_from_fields([x.decode('ascii') for x in first[8:13]], 0)
            if pnu in pnus:
                v = line.rstrip(b'\r\n').decode('utf-8-sig').split('|')
                if len(v) not in (76, 77): raise ValueError('Unexpected title schema')
                found[pnu].append({'mgmt_pk': v[0], 'pnu': pnu, 'building_name': v[7],
                    'dong_name': v[22], 'main_aux_label': v[24], 'main_purpose': v[35],
                    'purpose_detail': v[36], 'approval_date': v[60],
                    'raw_identity': v[8:13], 'related_lot_count': v[16]})
            if n % 2000000 == 0: print('title rows', n, flush=True)
    return dict(found), {'file': path.parent.name+'/'+path.name, 'rows': n, 'sha256': sha.hexdigest()}


def main():
    path = OUT/'named_object_mix_evidence.json.gz'
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    source_inventory = json.loads((LAB/'cheongju_named_object_mix.json').read_text(encoding='utf-8'))['source_inventory']
    for name, source in [('kapt_representative',kapt_pnu_xlsx()),('kapt_basic_info',kapt_info_xlsx())]:
        if hashlib.sha256(source.read_bytes()).hexdigest()!=source_inventory[name]['sha256']: raise ValueError('K-apt source changed')
    with gzip.open(path, 'rt', encoding='utf-8') as f: frozen = json.load(f)
    selected = sorted([r for r in frozen if r['decision']['evidence_class']=='cross_legal_dong_multiple_kapt_codes_review'], key=lambda r:r['building_key'])
    if len(selected)!=17 or any(r['asset_type']!='apartment' for r in selected): raise ValueError('Frozen cohort changed')
    ids = [r['stats_id'] for r in selected]
    sql = '''SELECT s.id stats_id,t.beopjungri_code,t.lot_number,to_char(t.contract_date,'YYYY-MM') contract_month,count(*) transactions
      FROM collective_building_stats s JOIN collective_transactions t USING(building_key,asset_type)
      WHERE s.id IN :ids AND t.is_valid=true AND t.unit_price>0 AND t.contract_date BETWEEN s.period_start AND s.period_end
      GROUP BY s.id,t.beopjungri_code,t.lot_number,to_char(t.contract_date,'YYYY-MM')
      ORDER BY s.id,t.beopjungri_code,t.lot_number,contract_month'''
    engine = get_collective_engine()
    try:
        if engine.url.host not in ('localhost','127.0.0.1','::1'): raise RuntimeError('Local database required')
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text("SET LOCAL statement_timeout='60s'"))
            conn.execute(text('SET LOCAL enable_mergejoin=off'))
            months = [dict(r._mapping) for r in conn.execute(text(sql).bindparams(bindparam('ids',expanding=True)), {'ids':ids})]
            snap = dict(conn.execute(text('SELECT current_database() db,current_timestamp observed_at,txid_current_snapshot() snapshot')).one()._mapping)
    finally: engine.dispose()
    by_id = defaultdict(list)
    for m in months: by_id[m['stats_id']].append(m)
    pnus = {p for r in selected for p in r['observed_pnus']}
    titles, meta = scan_titles(title_path('2026-07'), pnus)
    inventory = json.loads((LAB/'cheongju_relation_source_evidence.json').read_text(encoding='utf-8'))['raw_inventory']
    expected = next(r for r in inventory if r.get('snapshot')=='2026-07' and r['source']=='title')
    if meta['sha256']!=expected['sha256'] or meta['rows']!=expected['rows']: raise ValueError('Title source changed')
    cases = []
    for i,r in enumerate(selected,1):
        if sum(m['transactions'] for m in by_id[r['stats_id']])!=r['transaction_count']: raise ValueError('Transaction baseline changed')
        if {address_pnu(m['beopjungri_code'],m['lot_number']) for m in by_id[r['stats_id']]}!=set(r['observed_pnus']): raise ValueError('Observed address baseline changed')
        sites = []
        for p in r['address_review_partitions']:
            if p['address_identity'][0]!='pnu': raise ValueError('Unparseable address requires separate review')
            pnu = p['address_identity'][1]
            codes = sorted({k['danji_code'] for k in r['raw_kapt_representative_rows'] if k['pnu']==pnu and k['danji_code']})
            info = [k for k in r['raw_kapt_basic_info'] if k['단지코드'].strip() in codes]
            raw = titles.get(pnu,[])
            site = {'pnu':pnu, 'transactions':p['transactions'], 'observed_addresses':p['address_groups'],
                    'monthly_transaction_observations':[m for m in by_id[r['stats_id']] if address_pnu(m['beopjungri_code'],m['lot_number'])==pnu],
                    'contract_months':sorted({m['contract_month'] for m in by_id[r['stats_id']] if address_pnu(m['beopjungri_code'],m['lot_number'])==pnu}),
                    'kapt_codes':codes, 'names':sorted({k['단지명'].strip() for k in info if k['단지명'].strip()}),
                    'approval_dates':sorted({k['사용승인일'].strip() for k in info if k['사용승인일'].strip()}),
                    'road_addresses':sorted({k['도로명주소'].strip() for k in info if k['도로명주소'].strip()}),
                    'raw_kapt_basic_info':info, 'raw_titles':raw,
                    'communal_housing_title_count':sum(k['main_purpose']=='공동주택' for k in raw),
                    'title_approval_dates':sorted({k['approval_date'].strip() for k in raw if k['main_purpose']=='공동주택' and k['approval_date'].strip()}),
                    'apartment_detail_mentions':sum('아파트' in k['purpose_detail'] for k in raw)}
            site['kapt_approval_dates_seen_in_title'] = sorted(set(site['approval_dates']) & set(site['title_approval_dates']))
            if sum(m['transactions'] for m in by_id[r['stats_id']] if address_pnu(m['beopjungri_code'],m['lot_number'])==pnu)!=site['transactions']: raise ValueError('Partition counts changed')
            sites.append(site)
        pairs = [compare_sites(a,b) for a,b in combinations(sites,2)]
        cases.append({'case_id':f'apt-site-{i:02d}', 'building_key':r['building_key'], 'district':r['district'],
            'transaction_count':r['transaction_count'], 'as_of_month':r['as_of_month'],
            'sites':sites, 'site_pairs':pairs, 'supported_distinct_site_pairs':sum(p['assessment']=='distinct_sites_supported_membership_unverified' for p in pairs),
            'baseline_price_mart':r['baseline_price_mart'], 'baseline_attribute_rows':r['existing_attribute_rows'],
            'shadow_gate':shadow_gate(r['address_review_partitions']),
            'membership_status':'unverified', 'code_change_history_status':'not_available_in_static_kapt_source'})
    pks = [t['mgmt_pk'] for ts in titles.values() for t in ts]
    checks = {'cohort_17_preserved':len(cases)==17,'source_title_hash_replayed':True,'kapt_source_hashes_replayed':True,
              'raw_title_pks_unique':len(pks)==len(set(pks)),
              'all_transactions_conserved':sum(c['shadow_gate']['transactions'] for c in cases)==sum(r['transaction_count'] for r in selected),
              'no_product_assignment':all(c['shadow_gate']['new_object_key'] is None and not c['shadow_gate']['production_apply'] for c in cases),
              'prior_evidence_unchanged':hashlib.sha256(path.read_bytes()).hexdigest()==before}
    if not all(checks.values()): raise AssertionError(checks)
    brief = [{'case_id':c['case_id'],'district':c['district'],'transactions':c['transaction_count'],
              'address_partitions':len(c['sites']),'supported_distinct_site_pairs':c['supported_distinct_site_pairs'],
              'price_mart_present':c['baseline_price_mart'] is not None,
              'sites':[{'names':s['names'],'kapt_codes':s['kapt_codes'],'observed_address_labels':sorted({' '.join(str(g[k] or '') for k in ('addr4','lot_number')) for g in s['observed_addresses']}),
                        'approval_dates':s['approval_dates'],'transactions':s['transactions'],'communal_housing_title_count':s['communal_housing_title_count'],
                        'kapt_approval_dates_seen_in_title':s['kapt_approval_dates_seen_in_title']} for s in c['sites']]} for c in cases]
    report = {'audit_version':'cheongju-apartment-site-review-v1','run_date':date.today().isoformat(),
              'keys':len(cases),'address_partitions':sum(len(c['sites']) for c in cases),
              'transactions':sum(c['transaction_count'] for c in cases),
              'keys_with_supported_distinct_site_pair':sum(c['supported_distinct_site_pairs']>0 for c in cases),
              'site_pair_assessments':dict(Counter(p['assessment'] for c in cases for p in c['site_pairs'])),
              'selected_pnus':len(pnus),'raw_title_rows':len(pks), 'cases':brief,'checks':checks,
              'sites_without_kapt_evidence':sum(not s['kapt_codes'] for c in cases for s in c['sites']),
              'sites_with_kapt_approval_date_replayed_in_title':sum(bool(s['kapt_approval_dates_seen_in_title']) for c in cases for s in c['sites']),
              'source_inventory':{'title':meta,'kapt':source_inventory},
              'provenance':{'protected_input_sha256':before,'evidence_content_sha256':canonical_hash(cases),
                            'query_sql_sha256':canonical_hash(sql),'query_output_sha256':canonical_hash(months),
                            'database_snapshot':snap,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
              'limitations':['Static K-apt files provide no code validity/change history.',
                             'Common transaction months support contemporary address use; they do not certify transaction membership or disprove administrative change.',
                             'Title address co-location and apartment purpose do not certify danji membership or additional parcel relations.',
                             'Latest 2026-07 title source is not historical title availability or a complete site boundary.',
                             'No production object, price, attribute, statistics or regression changes.']}
    with gzip.open(OUT/'apartment_site_review_evidence.json.gz','wt',encoding='utf-8') as f: json.dump(cases,f,ensure_ascii=False)
    (LAB/'cheongju_apartment_site_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','source_inventory','provenance','limitations')},ensure_ascii=True),flush=True)


if __name__=='__main__': main()
