"""Read-only source-input preview; never assigns a title to a transaction or danji."""
import gzip
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/research/cheongju_ledger'
LAB = ROOT/'docs/lab'
CONTRACT = 'ledger-consumer-input-draft-v1'


def price_input(identity_status, pnu, price):
    if identity_status != 'canonical_address' or pnu is None:
        return {'status':'identity_blocked','value_krw_per_m2':None,'price_year':None}
    if price is None:
        return {'status':'not_observed_in_selected_snapshot','value_krw_per_m2':None,'price_year':None}
    year, raw_year, raw_price, source_status = price
    base = {'price_year':year,'raw_year':raw_year,'raw_price':raw_price,'source_status':source_status,
            'value_krw_per_m2':None}
    if raw_price and set(raw_price.strip()) == {'*'}:
        return {**base,'status':'source_overflow'}
    try:
        value = Decimal(raw_price)
    except InvalidOperation:
        return {**base,'status':'missing_or_nonpositive'}
    if not value.is_finite() or value <= 0:
        return {**base,'status':'missing_or_nonpositive'}
    if year is None:
        return {**base,'status':'unknown_price_year'}
    return {**base,'status':'positive_known_year','value_krw_per_m2':format(value,'f')}


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)


def main():
    paths = [OUT/'building_source_staging_v2_full.sqlite',OUT/'building_relation_staging.sqlite']
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    v2, v1 = [readonly(p) for p in paths]
    rows = []; batches = []; checks = {}
    for snapshot, in v2.execute('SELECT snapshot FROM source_batch ORDER BY snapshot'):
        title_manifest = json.loads(v2.execute('SELECT manifest FROM source_batch WHERE snapshot=?',(snapshot,)).fetchone()[0])
        prices = {pnu:(year, raw_year, raw_price, status) for pnu,year,raw_year,raw_price,status in
                  v1.execute('SELECT pnu,price_year,raw_year,raw_price,status FROM assessed_price_observation WHERE snapshot=?',(snapshot,))}
        manifest = json.loads(v1.execute('SELECT manifest FROM source_snapshot WHERE id=?',(snapshot,)).fetchone()[0])
        statuses = Counter(); unique_priced_pnus = set(); count = 0
        for pk,version,status,pnu,source_hash in v2.execute('''SELECT o.pk,v.raw_hash,o.identity_status,r.pnu,b.content_hash
          FROM title_observation o JOIN source_version v ON o.version=v.id JOIN source_batch b USING(snapshot)
          LEFT JOIN canonical_address_relation r ON o.snapshot=r.snapshot AND o.pk=r.pk WHERE o.snapshot=?''',(snapshot,)):
            price = price_input(status,pnu,prices.get(pnu))
            if price['status']=='positive_known_year':
                unique_priced_pnus.add(pnu)
            statuses[price['status']] += 1; count += 1
            rows.append({'contract_version':CONTRACT,'record_kind':'title_source_input',
                         'normalization_rule':title_manifest['normalization_rule'],
                         'title_source_sha256':title_manifest['source_sha256'],
                         'mgmt_pk':pk,'title_snapshot':snapshot,'raw_version_hash':version,
                         'identity_status':status,'address_pnu':pnu,
                         'relation_kind':'title_address' if pnu else None,
                         'title_batch_content_hash':source_hash,'trait_source_sha256':manifest['trait_sha256'],
                         'trait_asof':manifest['trait_cutoff'],'temporal_policy':'same_year_research_only',
                         'price':price,'consumer_assignment':'unassigned',
                         'transaction_match_status':'not_evaluated','danji_match_status':'not_evaluated',
                         'regression_eligibility':'not_evaluated'})
        batches.append({'snapshot':snapshot,'title_input_rows':count,'price_statuses':dict(statuses),
                        'distinct_positive_price_pnus':len(unique_priced_pnus)})
    checks['one_input_per_title_observation'] = len(rows)==v2.execute('SELECT COUNT(*) FROM title_observation').fetchone()[0]
    checks['input_keys_unique'] = len({(r['mgmt_pk'],r['title_snapshot']) for r in rows})==len(rows)
    checks['versioned_source_provenance_present'] = all(r['normalization_rule']=='cheongju-source-identity-v2.1' and len(r['title_source_sha256'])==64 for r in rows)
    checks['no_identity_blocked_price'] = all(r['price']['value_krw_per_m2'] is None for r in rows if r['identity_status']!='canonical_address')
    checks['no_invented_product_assignment'] = all(r['consumer_assignment']=='unassigned' for r in rows)
    checks['positive_prices_have_matching_year'] = all(r['price']['price_year']==int(r['title_snapshot'][:4]) for r in rows if r['price']['value_krw_per_m2'] is not None)
    v1.close(); v2.close()
    checks['both_input_databases_unchanged'] = hashes==[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    if not all(checks.values()): raise AssertionError(checks)
    with gzip.open(OUT/'ledger_consumer_input_preview.json.gz','wt',encoding='utf-8') as stream:
        json.dump(rows,stream,ensure_ascii=False)
    report = {'run_date':date.today().isoformat(),'contract_version':CONTRACT,'batches':batches,'checks':checks,
              'limitations':['Title-address source inputs, not matched transactions or assigned danji regression rows.',
                             'Same-year research policy, not historical information availability certification.',
                             'Repeated titles can reference one parcel; title row counts are not parcel counts or summed site prices.',
                             'No production pipeline or regression eligibility changes.']}
    (LAB/'ledger_consumer_input_preview.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__': main()
