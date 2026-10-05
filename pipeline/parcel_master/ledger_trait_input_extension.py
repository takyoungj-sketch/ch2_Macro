"""Extend the local consumer preview with all 19 retained trait-cache columns."""
import csv
import gzip
import hashlib
import json
from collections import Counter
from datetime import date

from ledger_consumer_input_preview import ROOT, OUT, LAB, readonly
from ledger_staging import attributes
from building_source_staging_v2 import digest

FIELDS = ('pnu','bjd','lot','year','month','jimok_code','jimok_label','area','zone1_code','zone1_label',
          'zone2_code','zone2_label','use_code','height_code','shape_code','road_code','price','trait_asof','trait_source')


def trait_input(status, pnu, raw, version=None):
    if status != 'canonical_address' or pnu is None:
        return {'status':'identity_blocked','raw':None,'attribute_version_hash':None}
    if raw is None:
        return {'status':'not_observed_in_selected_snapshot','raw':None,'attribute_version_hash':None}
    if set(raw) != set(FIELDS) or raw['pnu'] != pnu or raw['bjd'] != pnu[:10]:
        raise ValueError('Trait identity/schema conflict')
    normalized = attributes(raw); normalized.pop('price')
    h = digest(normalized)
    if version is None or version != h:
        raise ValueError('Existing attribute version differs')
    return {'status':'observed','raw':dict(raw),'raw_record_hash':digest(raw),
            'attribute_version_hash':h,'attribute_normalization':'building-relation-v1',
            'raw_code_policy':'preserve_strings_and_labels_no_cross_year_imputation'}


def main():
    preview_path = OUT/'ledger_consumer_input_preview.json.gz'
    before = hashlib.sha256(preview_path.read_bytes()).hexdigest()
    with gzip.open(preview_path,'rt',encoding='utf-8') as stream:
        inputs = json.load(stream)
    db_path = OUT/'building_relation_staging.sqlite'; db_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
    db = readonly(db_path); batches = []; output = []; checks = {}
    for snapshot in sorted({r['title_snapshot'] for r in inputs}):
        selected = [r for r in inputs if r['title_snapshot']==snapshot]
        pnus = {r['address_pnu'] for r in selected if r['address_pnu']}
        path = OUT/f'traits_{snapshot[:4]}.csv.gz'
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if any(r['trait_source_sha256'] != sha for r in selected):
            raise ValueError('Frozen trait input differs')
        records = {}
        with gzip.open(path,'rt',encoding='utf-8',newline='') as stream:
            reader = csv.DictReader(stream)
            if set(reader.fieldnames) != set(FIELDS): raise ValueError('Unexpected retained trait fields')
            for raw in reader:
                if raw['pnu'] in pnus:
                    if raw['pnu'] in records: raise ValueError('Duplicate trait PNU')
                    records[raw['pnu']] = raw
        versions = {pnu:h for pnu,h in db.execute('SELECT o.pnu,v.hash FROM parcel_observation o JOIN parcel_version v ON o.version=v.id WHERE o.snapshot=?',(snapshot,))}
        statuses = Counter(); missing_labels = Counter(); blank_codes = Counter()
        for row in selected:
            trait = trait_input(row['identity_status'], row['address_pnu'], records.get(row['address_pnu']), versions.get(row['address_pnu']))
            output.append({**row,'contract_version':'ledger-consumer-input-draft-v2','traits':trait})
            statuses[trait['status']] += 1
            if trait['raw']:
                for name in ('jimok_label','zone1_label','zone2_label'):
                    if not trait['raw'][name]: missing_labels[name] += 1
                for name in ('jimok_code','zone1_code','zone2_code','use_code','height_code','shape_code','road_code'):
                    if trait['raw'][name].strip() in ('','0'): blank_codes[name] += 1
        batches.append({'snapshot':snapshot,'input_rows':len(selected),'trait_statuses':dict(statuses),
                        'distinct_observed_pnus':len(records),'blank_labels_in_title_inputs':dict(missing_labels),
                        'blank_or_zero_codes_in_title_inputs':dict(blank_codes)})
        print('extended traits',snapshot,dict(statuses),flush=True)
    db.close()
    checks['row_count_and_keys_preserved'] = len(output)==len(inputs) and len({(r['mgmt_pk'],r['title_snapshot']) for r in output})==len(inputs)
    checks['identity_blocked_has_no_traits'] = all(r['traits']['raw'] is None for r in output if r['identity_status']!='canonical_address')
    checks['all_observed_records_keep_19_columns'] = all(set(r['traits']['raw'])==set(FIELDS) for r in output if r['traits']['status']=='observed')
    checks['existing_preview_and_database_unchanged'] = hashlib.sha256(preview_path.read_bytes()).hexdigest()==before and hashlib.sha256(db_path.read_bytes()).hexdigest()==db_hash
    keyed = {(r['title_snapshot'],r['mgmt_pk']):r for r in inputs}
    checks['prices_and_product_assignment_unchanged'] = all(keyed[(r['title_snapshot'],r['mgmt_pk'])]['price']==r['price'] and r['consumer_assignment']=='unassigned' for r in output)
    if not all(checks.values()): raise AssertionError(checks)
    with gzip.open(OUT/'ledger_consumer_input_traits_v2.json.gz','wt',encoding='utf-8') as stream:
        json.dump(output,stream,ensure_ascii=False)
    report = {'run_date':date.today().isoformat(),'contract_version':'ledger-consumer-input-draft-v2',
              'retained_cache_fields':list(FIELDS),'batches':batches,'checks':checks,
              'limitations':['All retained cache columns, not every original SHP/DBF field or geometry.',
                             'Same-year title-address research input, not transaction or danji assignment.',
                             'Missing labels and zero codes are preserved; no cross-year name imputation.']}
    (LAB/'ledger_consumer_input_traits_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__=='__main__': main()
