"""Branch frozen city ledger and publish fields from the same original title file."""
import hashlib
import json
import sqlite3
import sys
from time import perf_counter

from integrated_ledger_v2 import connect, ingest, consumer, digest
from ledger_identity_v2 import identify
from ledger_release_cli import open_ledger
from run_cheongju_integrated_ledger_v2 import OUT, LAB, file_hash
from ledger_consumer_input_preview import ROOT
from ledger_supply_artifacts import write_json_atomic
sys.path.insert(0,str(ROOT/'pipeline'))
from parcel_master.paths import TITLE_COLS, title_path
from parcel_master.load_title_pilot import _row_from_rec

EXTENSION='original-title-product-fields-v1'
TARGET=OUT/'integrated_ledger_v2_cheongju_product.sqlite'
RELEASE='cheongju-city-2026-07-product-fields-v1'


def product_row(fields,snapshot):
    # Reuse the existing product normalization, including parking counts only.
    if identify([fields[k] for k in ('sigungu_code','bjd_code','plat_gb','bun','ji')])['status']!='canonical_address':
        raise ValueError('Canonical title required for product projection')
    row=_row_from_rec(fields,snapshot)
    if row is None:raise ValueError('Canonical title required for product projection')
    return row


def main():
    start=perf_counter();source=OUT/'integrated_ledger_v2_cheongju.sqlite';original_hash=file_hash(source)
    original=open_ledger(source)
    if not TARGET.exists():
        destination=sqlite3.connect(TARGET)
        original.backup(destination);destination.close()
    original.close();db=connect(TARGET)
    base='cheongju-city-2026-07-identity-2.2'
    manifest=json.loads(db.execute('SELECT manifest FROM release WHERE id=?',(base,)).fetchone()[0])
    buildings={pk:{'raw':json.loads(raw),'attributes':json.loads(attrs)} for pk,raw,attrs in db.execute('''
      SELECT o.pk,r.raw,a.payload FROM building_observation o JOIN building_raw r ON r.pk=o.pk AND r.hash=o.raw_hash
      JOIN building_attribute a ON a.pk=o.pk AND a.hash=o.attribute_hash WHERE o.release_id=?''',(base,))}
    targets=set(buildings);found=set();sha=hashlib.sha256();count=0
    with title_path('2026-07').open('rb') as f:
        for count,line in enumerate(f,1):
            sha.update(line);pk=line.split(b'|',1)[0].decode('ascii').strip()
            if pk not in targets:continue
            if pk in found:raise ValueError('Duplicate original title PK')
            parts=line.rstrip(b'\r\n').decode('utf-8-sig').split('|')
            if len(parts) not in (76,77):raise ValueError('Unknown source layout')
            rec={name:parts[index] for name,index in TITLE_COLS.items()}
            if parts[8:13]!=buildings[pk]['raw']['raw_identity_fields']:raise ValueError('Original identity differs')
            buildings[pk]['raw']={**buildings[pk]['raw'],'mgmt_pk':pk,'product_fields':rec,'product_fields_policy':EXTENSION}
            found.add(pk)
            if count%2000000==0:print('original title fields scanned',count,flush=True)
    if found!=targets or sha.hexdigest()!=manifest['sources']['title']['sha256']:raise ValueError('Original scope/hash changed')
    traits={pnu:{'raw':json.loads(raw),'original_dbf':json.loads(original_dbf) if original_dbf else None}
            for pnu,raw,original_dbf in db.execute('SELECT pnu,raw,original_dbf FROM parcel_observation WHERE release_id=?',(base,))}
    manifest={**manifest,'sources':{**manifest['sources'],'title':{**manifest['sources']['title'],
       'preservation':'original_selected_fields_and_product_fields_v1','product_fields_columns':TITLE_COLS}},'field_extension':EXTENSION}
    before_attrs=db.execute('SELECT count(*) FROM building_attribute').fetchone()[0]
    inserted=ingest(db,RELEASE,4,buildings,traits,manifest)
    replay=ingest(db,RELEASE,4,buildings,traits,manifest) is False
    sample=next(pk for pk in sorted(targets) if consumer(db,pk)['identity_status']=='canonical_address')
    c=consumer(db,sample)
    checks={'all_title_fields_preserved':len(found)==141252,'release_replay_idempotent':replay,
            'attribute_versions_unchanged':db.execute('SELECT count(*) FROM building_attribute').fetchone()[0]==before_attrs,
            'original_city_database_unchanged':file_hash(source)==original_hash,
            'foreign_keys_clean':not db.execute('PRAGMA foreign_key_check').fetchall(),
            'integrity':db.execute('PRAGMA quick_check').fetchone()[0]=='ok',
            'consumer_field_extension_present':c['building']['value']['raw']['product_fields_policy']==EXTENSION,
            'no_product_permission':not c['building']['permissions']['product_enrichment']}
    if not all(checks.values()):raise AssertionError(checks)
    report={'extension':EXTENSION,'base_release':base,'published_release':RELEASE,'source_rows_scanned':count,
            'extended_building_observations':len(found),'trait_observations':len(traits),'new_release_inserted':inserted,
            'source_title_sha256':sha.hexdigest(),'original_city_database_sha256':original_hash,
            'checks':checks,'sqlite_bytes':TARGET.stat().st_size,'elapsed_seconds':perf_counter()-start,
            'limitations':['Same frozen original and schema; old city DB preserved and experimental supply branch created.',
                           'Original columns preserved as strings; existing product normalization reused only in shadow comparison.',
                           'No new membership, representative selection, aggregation permission or production application.']}
    db.close();write_json_atomic(LAB/'cheongju_product_field_extension.json',report)
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
