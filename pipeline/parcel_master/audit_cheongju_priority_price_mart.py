"""Source review of six priority price-mart keys; creates review proposals only."""
import csv
import gzip
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import bindparam, text

from ledger_consumer_input_preview import ROOT, OUT, LAB
from audit_cheongju_address_pair_impact import canonical_hash
from audit_cheongju_product_link_candidates import address_pnu
from audit_cheongju_relation_source_evidence import pnu_from_fields
from ledger_trait_raw_attributes import scan as scan_dbf

sys.path.insert(0, str(ROOT/'pipeline'))
from collective.db_utils import get_collective_engine
from parcel_master.db_utils import get_parcel_engine
from parcel_master.paths import title_path, land_price_csv, kapt_pnu_xlsx, kapt_info_xlsx
from collective.building_keys import derive_building_key


def read(factory, queries, params):
    engine = factory()
    try:
        if engine.url.host not in ('localhost', '127.0.0.1', '::1'):
            raise RuntimeError('Local database required')
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text("SET LOCAL statement_timeout='60s'"))
            result = {}
            for name, sql in queries.items():
                statement = text(sql)
                for key in params:
                    if ':'+key in sql:
                        statement = statement.bindparams(bindparam(key, expanding=True))
                result[name] = [dict(r._mapping) for r in conn.execute(statement, params)]
            snapshot = dict(conn.execute(text('SELECT current_database() db,current_timestamp observed_at,txid_current_snapshot() snapshot')).one()._mapping)
            return result, snapshot
    finally:
        engine.dispose()


def scan_title_addresses(path, pnus, processed_pks):
    found = defaultdict(list)
    sha = hashlib.sha256()
    n = 0
    with path.open('rb') as stream:
        for n, line in enumerate(stream, 1):
            sha.update(line)
            first = line.rstrip(b'\r\n').split(b'|', 13)
            pk = first[0].decode('ascii').strip()
            pnu = pnu_from_fields([v.decode('ascii') for v in first[8:13]], 0)
            if pnu in pnus or pk in processed_pks:
                values = line.rstrip(b'\r\n').decode('utf-8-sig').split('|')
                if len(values) not in (76,77):
                    raise ValueError('Unexpected title schema')
                found[pk].append({'mgmt_pk': pk, 'pnu': pnu, 'raw_identity': values[8:13],
                                  'building_name': values[7], 'dong_name': values[22],
                                  'ledger_kind': values[2], 'main_aux_code': values[23],
                                  'main_aux_label': values[24], 'main_purpose': values[35],
                                  'purpose_detail': values[36], 'related_lot_count': values[16]})
            if n % 2000000 == 0:
                print('raw title rows', n, flush=True)
    return dict(found), {'file': path.parent.name+'/'+path.name,
                         'sha256': sha.hexdigest(), 'rows': n}


def scan_price(path, targets):
    result = defaultdict(list)
    with path.open(encoding='cp949', newline='') as stream:
        reader = csv.DictReader(stream)
        required = {'고유번호', '기준연도', '공시지가', '공시일자'}
        if not required <= set(reader.fieldnames or []):
            raise ValueError('Unexpected price source schema')
        count = 0
        for count, row in enumerate(reader, 1):
            pnu = row['고유번호'].strip()
            if pnu in targets:
                result[pnu].append(row)
    return dict(result), {'file': str(path.relative_to(ROOT)),
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'rows': count}


def scan_kapt(path, targets, codes):
    # Preserve duplicate rows; do not use the loader's drop_duplicates policy.
    frame = pd.read_excel(path, skiprows=1, dtype=str).fillna('')
    frame.columns = [str(c).strip() for c in frame.columns]
    pnu_col = next(c for c in frame.columns if '고유' in c or c == '고유번호')
    code_col = next(c for c in frame.columns if '단지' in c or 'kapt' in c.lower())
    rows = []
    for row in frame.to_dict(orient='records'):
        pnu, code = str(row[pnu_col]).strip(), str(row[code_col]).strip()
        if pnu in targets or code in codes:
            rows.append({'pnu': pnu, 'danji_code': code, 'raw': row})
    return rows, {'file': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                  'rows': len(frame), 'pnu_column': pnu_col, 'danji_column': code_col}


def price_agrees(raw_rows, year, price):
    matches = []
    for row in raw_rows:
        try:
            if int(row['기준연도']) == int(year) and Decimal(row['공시지가'].replace(',', '')) == Decimal(str(price)):
                matches.append(row)
        except (ValueError, InvalidOperation):
            pass
    return bool(matches)


def proposal(observed_pnus, mart_pnu, linked_kapt_pnus, observed_kapt_codes, has_attributes, legal_codes=()):
    """Evidence conflicts create proposals, never a replacement PNU."""
    reasons = ['stats_component_max_pnu_not_observed', 'physical_membership_unverified']
    if linked_kapt_pnus and not set(linked_kapt_pnus) <= set(observed_pnus):
        reasons.append('existing_kapt_pnu_outside_observed_transaction_candidates')
    if len(set(observed_kapt_codes)) > 1:
        reasons.append('multiple_kapt_codes_on_observed_addresses')
    if not has_attributes:
        reasons.append('no_existing_building_attribute_row')
    if len(set(legal_codes)) > 1:
        reasons.append('named_object_key_spans_multiple_legal_dongs')
    return {'status': 'review_required', 'reasons': reasons, 'baseline_mart_pnu': mart_pnu,
            'candidate_pnus': sorted(set(observed_pnus)), 'proposed_representative_pnu': None,
            'candidate_membership_status': 'unverified',
            'proposed_action': ('review_object_key_partitions_before_representative_change'
                                if len(set(legal_codes))>1 else
                                'source_and_membership_review_before_versioned_representative_change'),
            'production_apply': False}


def main():
    input_path = OUT/'address_pair_impact_evidence.json.gz'
    before = hashlib.sha256(input_path.read_bytes()).hexdigest()
    with gzip.open(input_path, 'rt', encoding='utf-8') as stream:
        rows = json.load(stream)['residential']
    selected = sorted([r for r in rows if r['window_years']==7 and
                       'price_mart_uses_unobserved_stats_pnu' in r['flags']], key=lambda r:(r['asset_type'],r['product_key']))
    if len(selected) != 6:
        raise AssertionError('Priority cohort changed; review scope before proceeding')
    pnus = {r['strict_stats_pnu'] for r in selected} | {p for r in selected for p in r['observed_cheongju_pnus']}
    keys = [r['product_key'] for r in selected]
    collective, csnap = read(get_collective_engine, {
        'mart': 'SELECT * FROM collective_building_assessed_land_price WHERE building_key IN :keys',
        'attributes': 'SELECT * FROM collective_building_attributes WHERE building_key IN :keys',
        'transactions': '''SELECT s.building_key,s.asset_type,t.beopjungri_code,t.lot_number,t.building_name,
          t.addr1,t.addr2,t.addr3,t.addr4,count(*) transactions,min(t.contract_date) first_contract,max(t.contract_date) last_contract
          FROM collective_building_stats s JOIN collective_transactions t USING(building_key,asset_type)
          WHERE s.id IN :ids AND t.is_valid=true AND t.unit_price>0 AND t.contract_date BETWEEN s.period_start AND s.period_end
          GROUP BY s.building_key,s.asset_type,t.beopjungri_code,t.lot_number,t.building_name,t.addr1,t.addr2,t.addr3,t.addr4''',
        'kapt': '''SELECT * FROM builder_master WHERE pnu IN :pnus OR danji_code IN
          (SELECT danji_code FROM collective_building_attributes WHERE building_key IN :keys)'''
    }, {'keys':keys, 'ids':[r['id'] for r in selected], 'pnus':sorted(pnus)})
    codes = {str(r['danji_code']).strip() for r in collective['kapt']}
    raw_kapt, kapt_meta = scan_kapt(kapt_pnu_xlsx(), pnus, codes)
    info_path = kapt_info_xlsx()
    frame = pd.read_excel(info_path, skiprows=1, dtype=str).fillna('')
    frame.columns = [str(c).strip() for c in frame.columns]
    raw_codes = {r['danji_code'] for r in raw_kapt} | codes
    raw_kapt_info = [r for r in frame.to_dict(orient='records') if str(r['단지코드']).strip() in raw_codes]
    info_meta = {'file':str(info_path.relative_to(ROOT)), 'sha256':hashlib.sha256(info_path.read_bytes()).hexdigest(),
                 'rows':len(frame), 'selected_rows':len(raw_kapt_info)}
    pnus.update(r['pnu'] for r in raw_kapt if re.fullmatch(r'4311[1-4][0-9]{5}[12][0-9]{8}', r['pnu']))
    parcel, psnap = read(get_parcel_engine, {
        'buildings': "SELECT * FROM building WHERE snapshot='2026-07' AND pnu IN :pnus",
        'prices': 'SELECT * FROM parcel_land_price WHERE pnu IN :pnus'
    }, {'pnus':sorted(pnus)})
    print('priority DB context', len(selected), 'keys', len(pnus), 'PNU', len(parcel['buildings']), 'processed titles', flush=True)
    processed_pks = {r['mgmt_pk'] for r in parcel['buildings']}
    raw_titles, title_meta = scan_title_addresses(title_path('2026-07'), pnus, processed_pks)
    frozen = json.loads((LAB/'cheongju_relation_source_evidence.json').read_text(encoding='utf-8'))['raw_inventory']
    expected = next(r for r in frozen if r.get('snapshot')=='2026-07' and r['source']=='title')
    if title_meta['sha256'] != expected['sha256'] or title_meta['rows'] != expected['rows']:
        raise ValueError('Frozen title source changed')
    if any(len(v)!=1 for v in raw_titles.values()) or not processed_pks <= set(raw_titles):
        raise ValueError('Raw title PK duplicate or missing')
    raw_prices, price_meta = scan_price(land_price_csv('43'), pnus)
    traits, trait_meta = {}, []
    sources = sorted((ROOT/'raw/raw addition/토지특성정보(브이월드)').glob('AL_D194_4311?_2026*.zip'))
    if len(sources)!=4:
        raise ValueError('Four city DBFs required')
    for path in sources:
        values, meta = scan_dbf(path, pnus)
        if set(traits) & set(values):
            raise ValueError('Duplicate cross-source trait PNU')
        traits.update(values); trait_meta.append(meta)
    by_pnu = defaultdict(list)
    for records in raw_titles.values():
        for r in records:
            by_pnu[r['pnu']].append(r)
    cases = []
    for index, row in enumerate(selected,1):
        key, asset = row['product_key'], row['asset_type']
        mart = next(r for r in collective['mart'] if r['building_key']==key and r['asset_type']==asset)
        if str(mart['representative_pnu']).strip()!=row['strict_stats_pnu']:
            raise ValueError('Priority mart changed')
        attrs = [r for r in collective['attributes'] if r['building_key']==key and r['asset_type']==asset]
        tx = [r for r in collective['transactions'] if r['building_key']==key and r['asset_type']==asset]
        observed = {address_pnu(r['beopjungri_code'],r['lot_number']) for r in tx}; observed.discard(None)
        if observed != set(row['observed_cheongju_pnus']) or sum(r['transactions'] for r in tx)!=row['eligible_transaction_count']:
            raise ValueError('Frozen transaction context changed')
        linked_codes = {str(r['danji_code']).strip() for r in attrs if r['danji_code']}
        linked_kapt = [r for r in raw_kapt if r['danji_code'] in linked_codes]
        observed_kapt = [r for r in raw_kapt if r['pnu'] in observed]
        legal_codes = {r['beopjungri_code'].strip() for r in tx}
        key_replay = all(derive_building_key(asset_type=asset, addr1=r['addr1'], addr2=r['addr2'],
                          addr3=r['addr3'], addr4=r['addr4'], building_name=r['building_name'],
                          lot_number=r['lot_number'], road_name=None)==key for r in tx)
        context_pnus = observed | {row['strict_stats_pnu']} | {r['pnu'] for r in linked_kapt}
        decision = proposal(observed, row['strict_stats_pnu'], [r['pnu'] for r in linked_kapt],
                            [r['danji_code'] for r in observed_kapt], bool(attrs), legal_codes)
        case = {'case_id': f'case-{index}', 'asset_type':asset, 'district':row['district'],
                'building_key':key, 'baseline_stats':row, 'baseline_price_mart':mart,
                'existing_attributes':attrs, 'transaction_addresses':tx, 'linked_kapt_raw':linked_kapt,
                'observed_address_kapt_raw':observed_kapt,
                'kapt_basic_info_raw':[r for r in raw_kapt_info if str(r['단지코드']).strip() in
                                       (linked_codes | {k['danji_code'] for k in observed_kapt})],
                'distinct_observed_legal_dongs':len(legal_codes), 'existing_named_key_reproduced':key_replay,
                'kapt_processed_context':[r for r in collective['kapt'] if r['pnu'] in context_pnus or r['danji_code'] in linked_codes],
                'raw_titles_by_pnu':{p:by_pnu.get(p,[]) for p in sorted(context_pnus)},
                'raw_prices_by_pnu':{p:raw_prices.get(p,[]) for p in sorted(context_pnus)},
                'processed_prices':[r for r in parcel['prices'] if r['pnu'] in context_pnus],
                'raw_traits_by_pnu':{p:traits[p] for p in sorted(context_pnus) if p in traits},
                'price_raw_pnu_year_value_agrees':price_agrees(raw_prices.get(row['strict_stats_pnu'],[]),mart['assessed_land_price_year'],mart['assessed_land_price']),
                'synthetic_address_raw_title_count':len(by_pnu.get(row['strict_stats_pnu'],[])),
                'proposal':decision}
        cases.append(case)
    summary_cases = [{'case_id':r['case_id'], 'asset_type':r['asset_type'], 'district':r['district'],
                      'transaction_count':r['baseline_stats']['eligible_transaction_count'],
                      'observed_pnu_candidates':len(r['proposal']['candidate_pnus']),
                      'existing_attribute_tiers':[a['match_tier'] for a in r['existing_attributes']],
                      'synthetic_address_raw_title_count':r['synthetic_address_raw_title_count'],
                      'linked_kapt_raw_count':len(r['linked_kapt_raw']),
                      'distinct_kapt_codes_on_observed_addresses':len({a['danji_code'] for a in r['observed_address_kapt_raw']}),
                      'distinct_observed_legal_dongs':r['distinct_observed_legal_dongs'],
                      'existing_named_key_reproduced':r['existing_named_key_reproduced'],
                      'synthetic_address_title_purposes':sorted({x['main_purpose'] for x in r['raw_titles_by_pnu'].get(r['baseline_stats']['strict_stats_pnu'],[])}),
                      'raw_kapt_basic_info_rows':len(r['kapt_basic_info_raw']),
                      'price_raw_pnu_year_value_agrees':r['price_raw_pnu_year_value_agrees'],
                      'price_source_label':r['baseline_price_mart']['source'],
                      'status':r['proposal']['status'],'reasons':r['proposal']['reasons']} for r in cases]
    checks = {'six_priority_keys_reviewed':len(cases)==6,
              'all_mart_values_replayed_from_raw_price':all(r['price_raw_pnu_year_value_agrees'] for r in cases),
              'all_existing_named_keys_reproduced_from_transaction_fields':all(r['existing_named_key_reproduced'] for r in cases),
              'all_observed_kapt_codes_have_raw_basic_info':all({k['danji_code'] for k in r['observed_address_kapt_raw']} <= {str(k['단지코드']).strip() for k in r['kapt_basic_info_raw']} for r in cases),
              'raw_title_pks_unique_and_processed_targets_present':all(len(v)==1 for v in raw_titles.values()) and processed_pks<=set(raw_titles),
              'prior_address_evidence_unchanged':hashlib.sha256(input_path.read_bytes()).hexdigest()==before,
              'no_automatic_pnu_change_or_apply':all(r['proposal']['proposed_representative_pnu'] is None and not r['proposal']['production_apply'] for r in cases)}
    if not all(checks.values()):
        raise AssertionError(checks)
    report = {'run_date_kst':datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat(),
              'review_version':'priority-price-mart-source-review-v1','cases':summary_cases,
              'counts':{'keys':len(cases),'source_price_replayed':sum(r['price_raw_pnu_year_value_agrees'] for r in cases),
                        'synthetic_address_with_raw_title':sum(r['synthetic_address_raw_title_count']>0 for r in cases),
                        'existing_attribute_missing':sum(not r['existing_attributes'] for r in cases),
                        'reasons':dict(Counter(f for r in cases for f in r['proposal']['reasons']))},
              'checks':checks,'source_inventory':{'title':title_meta,'price':price_meta,'kapt':kapt_meta,'kapt_basic_info':info_meta,'traits':trait_meta},
              'provenance':{'input_sha256':before,'database_snapshots':[csnap,psnap],
                            'code_sha256':hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
                            'building_key_code_sha256':hashlib.sha256((ROOT/'pipeline/collective/building_keys.py').read_bytes()).hexdigest(),
                            'query_output_sha256':canonical_hash([collective,parcel]),'evidence_content_sha256':canonical_hash(cases)},
              'limitations':['Source PNU/price/role replay is not independently verified danji membership.',
                             'Separate local read-only snapshots; no production audit or historical import log reconstruction.',
                             'A raw K-apt representative PNU is not the full parcel set or certified transaction membership.',
                             'Co-address titles and counts do not certify parent-child or additional-parcel relationships.',
                             'Six priority keys only; no city-wide reassignment, regression change, or price deletion.',
                             'Commercial road clusters have no same representative-PNU price mart; prior paired address audit remains the commercial evidence.']}
    with gzip.open(OUT/'priority_price_mart_source_evidence.json.gz','wt',encoding='utf-8') as stream:
        json.dump(cases,stream,ensure_ascii=False,default=str)
    queue = []
    for case in cases:
        partitions = []
        for pnu in case['proposal']['candidate_pnus']:
            transactions = [r for r in case['transaction_addresses'] if address_pnu(r['beopjungri_code'],r['lot_number'])==pnu]
            partitions.append({'observed_address_pnu':pnu,
                               'transactions':sum(r['transactions'] for r in transactions),
                               'transaction_address_groups':transactions,
                               'raw_title_pks':[r['mgmt_pk'] for r in case['raw_titles_by_pnu'].get(pnu,[])],
                               'raw_kapt_codes':sorted({r['danji_code'] for r in case['observed_address_kapt_raw'] if r['pnu']==pnu}),
                               'membership_status':'unverified', 'new_object_key':None})
        if sum(r['transactions'] for r in partitions)!=case['baseline_stats']['eligible_transaction_count']:
            raise AssertionError('Review partitions must conserve transaction counts')
        queue.append({'case_id':case['case_id'],'baseline_building_key':case['building_key'],
                      'asset_type':case['asset_type'],'baseline_price_mart':case['baseline_price_mart'],
                      'source_evidence_sha256':canonical_hash(case), 'observed_address_review_partitions':partitions,
                      **case['proposal']})
    with gzip.open(OUT/'priority_price_mart_review_queue.json.gz','wt',encoding='utf-8') as stream:
        json.dump(queue,stream,ensure_ascii=False,default=str)
    report['checks']['review_partition_transaction_counts_conserved'] = True
    report['review_queue_rows'] = len(queue)
    (LAB/'cheongju_priority_price_mart_source_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'cases':summary_cases,'counts':report['counts'],'checks':checks},ensure_ascii=True),flush=True)


if __name__=='__main__':
    main()
