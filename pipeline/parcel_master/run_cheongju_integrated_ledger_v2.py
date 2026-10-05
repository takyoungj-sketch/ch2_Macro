"""Frozen 4,000 PK inputs -> one local versioned supply database and replay QA."""
import csv
import gzip
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from time import perf_counter

from ledger_identity_v2 import VERSION, identify
from integrated_ledger_v2 import CONTRACT, NAMESPACE, connect, consumer, digest, fingerprint, ingest, restore

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/research/cheongju_ledger'
LAB = ROOT / 'docs/lab'


def file_hash(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)


def load_inputs():
    paths=[OUT/'building_source_staging_v2_full.sqlite',OUT/'building_relation_staging.sqlite',
           OUT/'ledger_consumer_input_traits_full_dbf.json.gz',OUT/'building_source_v2_raw_review_full.json.gz']
    hashes={p.name:file_hash(p) for p in paths}
    v2,v1=readonly(paths[0]),readonly(paths[1])
    baseline=json.loads((LAB/'cheongju_building_source_v2_full.json').read_text(encoding='utf-8'))
    pks={r[0] for r in v2.execute('SELECT pk FROM building_entity')}
    scope=hashlib.sha256('\n'.join(sorted(pks)).encode()).hexdigest()
    if len(pks)!=4000 or scope!=baseline['scope_sha256']:raise ValueError('Frozen cohort changed')
    with gzip.open(paths[2],'rt',encoding='utf-8') as f:preview=json.load(f)
    with gzip.open(paths[3],'rt',encoding='utf-8') as f:originals=json.load(f)['originals']
    selected={};changes=[]
    for snapshot,manifest in v2.execute('SELECT snapshot,manifest FROM source_batch ORDER BY snapshot'):
        tm=json.loads(manifest)
        vm=json.loads(v1.execute('SELECT manifest FROM source_snapshot WHERE id=?',(snapshot,)).fetchone()[0])
        inventory=json.loads((LAB/'cheongju_relation_source_evidence.json').read_text(encoding='utf-8'))['raw_inventory']
        expected=next(x for x in inventory if x['source']=='title' and x['snapshot']==snapshot)
        if tm['source_sha256']!=expected['sha256']:raise ValueError('Frozen original source manifest differs')
        attributes={pk:json.loads(payload) for pk,payload in v1.execute('SELECT o.pk,v.payload FROM building_observation o JOIN building_version v ON v.id=o.version WHERE o.snapshot=?',(snapshot,))}
        b={}
        for pk,raw,status,old_pnu in v2.execute('''SELECT o.pk,v.raw_payload,o.identity_status,r.pnu FROM title_observation o
          JOIN source_version v ON v.id=o.version LEFT JOIN canonical_address_relation r ON r.snapshot=o.snapshot AND r.pk=o.pk WHERE o.snapshot=?''',(snapshot,)):
            raw=json.loads(raw)
            if raw!=originals[snapshot][pk]:raise ValueError('Stored source differs from frozen original replay')
            b[pk]={'raw':raw,'attributes':attributes[pk]}
            new=identify(raw['raw_identity_fields'])
            if new['pnu']!=old_pnu or new['status']!=status:
                prior=next(x for x in preview if x['title_snapshot']==snapshot and x['mgmt_pk']==pk)
                changes.append({'snapshot':snapshot,'management_pk':pk,'old_pnu':old_pnu,'new_pnu':new['pnu'],
                                'old_status':status,'new_status':new['status'],'old_price_status':prior['price']['status'],
                                'old_trait_status':prior['traits']['status']})
        pnus={r[0] for r in v1.execute('SELECT pnu FROM parcel_observation WHERE snapshot=?',(snapshot,))}
        path=OUT/f'traits_{snapshot[:4]}.csv.gz'
        if file_hash(path)!=vm['trait_sha256']:raise ValueError('Frozen trait cache changed')
        cache={}
        with gzip.open(path,'rt',encoding='utf-8',newline='') as f:
            for row in csv.DictReader(f):
                if row['pnu'] in pnus:
                    if row['pnu'] in cache:raise ValueError('Duplicate cached parcel')
                    cache[row['pnu']]={'raw':row,'original_dbf':None}
        if set(cache)!=pnus:raise ValueError('Frozen trait observation scope differs')
        for row in preview:
            if row['title_snapshot']!=snapshot or row['traits']['status']!='observed':continue
            pnu=row['address_pnu'];old=cache[pnu]
            if old['raw']!=row['traits']['raw']:raise ValueError('Raw cached traits differ')
            payload=row['traits']['original_dbf']
            if old['original_dbf'] and old['original_dbf']!=payload:raise ValueError('Conflicting original parcel rows')
            old['original_dbf']=payload
        sources={'title':{'sha256':tm['source_sha256'],'source_snapshot':snapshot,'file':tm['source_file'],
                          'base_date':None,'collected_at':None,'preservation':'frozen_original_selected_fields'},
                 'traits':{'sha256':vm['trait_sha256'],'base_date':vm['trait_cutoff'],'collected_at':None,
                           'source_year':vm['trait_year'],'raw_dbf_zip_inventory':[r for r in inventory if r['source']=='traits' and snapshot[:4] in r['filename']]},
                 'processed_building':{'sha256':vm['building_sha256'],'base_date':None,'collected_at':None,
                                       'attribute_origin':'frozen_processed_extract_crosschecked_raw_area_fields'}}
        m={'identity_rule':VERSION,'pk_namespace':NAMESPACE,'title_snapshot':snapshot,'trait_year':vm['trait_year'],
           'districts':['43111','43112','43113','43114'],'expected_buildings':len(b),'expected_traits':len(cache),
           'scope_sha256':scope,'sources':sources,'temporal_policy':'same_year_research_only','cohort':'frozen_4000_management_pks'}
        selected[snapshot]=(b,cache,m)
    v1.close();v2.close()
    return selected,changes,paths,hashes


def main():
    started=perf_counter();inputs,changes,paths,hashes=load_inputs()
    db_path=OUT/'integrated_ledger_v2_4000.sqlite';db=connect(db_path)
    releases=[];checks={};batches=[]
    for ordinal,(snapshot,(b,p,m)) in enumerate(sorted(inputs.items()),1):
        release_id=f'cheongju-4000-{snapshot}-identity-2.2'
        start=perf_counter();ingest(db,release_id,ordinal,b,p,m)
        releases.append(release_id);before=fingerprint(db)
        checks[snapshot+'_idempotent']=ingest(db,release_id,ordinal,b,p,m) is False and fingerprint(db)==before
        batches.append({'snapshot':snapshot,'buildings':len(b),'traits':len(p),'identity_statuses':dict(Counter(identify(r['raw']['raw_identity_fields'])['status'] for r in b.values())),
                        'ingest_seconds':perf_counter()-start})
        print('integrated',snapshot,len(b),len(p),flush=True)
    # Idempotent full replay must not change an explicitly selected historical head.
    latest= fingerprint(db)
    for phase in ['sources','traits','buildings','published']:
        b,p,m=inputs['2026-07']
        try:ingest(db,'injected-failure',4,b,p,m,fail_at=phase)
        except RuntimeError:pass
        checks['failure_'+phase]=fingerprint(db)==latest
    original_outputs={pk:consumer(db,pk) for pk, in db.execute('SELECT pk FROM current_building')}
    restore(db,releases[0])
    checks['oldest_release_selected']=db.execute("SELECT value FROM state WHERE key='published_release'").fetchone()[0]==releases[0]
    restore(db,releases[-1]);checks['restore_latest_all_tables']=fingerprint(db)==latest
    outputs=[consumer(db,pk) for pk, in db.execute('SELECT pk FROM current_building ORDER BY pk')]
    checks['restore_latest_consumer_exact']=all(r==original_outputs[r['management_pk']] for r in outputs)
    checks['stale_buildings_not_current_observations']=all(r['traits']['value'] is None and r['price']['value']['value_krw_per_m2'] is None for r in outputs if not r['observed_in_selected_release'])
    checks['blocked_identity_no_price_or_traits']=all(r['traits']['value'] is None and r['price']['value']['value_krw_per_m2'] is None for r in outputs if r['identity_status']!='canonical_address')
    checks['no_product_or_regression_permission']=all(not field['permissions']['product_enrichment'] and not field['permissions']['regression'] for r in outputs for field in [r['building'],r['traits'],r['price']])
    checks['foreign_keys_clean']=not db.execute('PRAGMA foreign_key_check').fetchall()
    checks['sqlite_integrity']=db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    tables={r[0]:db.execute('SELECT count(*) FROM '+r[0]).fetchone()[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    checks['zero_main_lot_never_canonical']=db.execute("SELECT count(*) FROM address_relation WHERE substr(pnu,12,4)='0000'").fetchone()[0]==0
    db.close();checks['all_frozen_inputs_unchanged']=hashes=={p.name:file_hash(p) for p in paths}
    if not all(checks.values()):raise AssertionError(checks)
    for name,value in [('integrated_ledger_identity_impact.json.gz',changes),('integrated_ledger_consumer_4000.json.gz',outputs)]:
        with gzip.open(OUT/name,'wt',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False)
    report={'rule_version':VERSION,'consumer_contract':CONTRACT,'cohort_management_pks':4000,'batches':batches,
            'identity_impact':{'changed_observations':len(changes),'by_new_status':dict(Counter(r['new_status'] for r in changes)),
                               'unique_changed_management_pks':len({r['management_pk'] for r in changes}),
                               'prior_price_statuses':dict(Counter(r['old_price_status'] for r in changes)),
                               'prior_trait_statuses':dict(Counter(r['old_trait_status'] for r in changes))},
            'tables':tables,'consumer':{'records':len(outputs),'observed_in_selected_release':sum(r['observed_in_selected_release'] for r in outputs),
                                       'last_seen_not_observed':sum(not r['observed_in_selected_release'] for r in outputs),
                                       'price_statuses':dict(Counter(r['price']['trust_state'] for r in outputs))},
            'checks':checks,'frozen_inputs_sha256':hashes,'sqlite_bytes':db_path.stat().st_size,'elapsed_seconds':perf_counter()-started,
            'limitations':['Biased 4,000-PK cohort, not city-wide exception rates.','Local source supply; no object membership, product enrichment or regression adoption.',
                           'Source base dates/collection dates remain null when unknown; title snapshot month is not legal effect date.',
                           'Building attributes retain explicitly marked processed provenance; source raw is selected original fields.',
                           'Original DBF payload preserved where already captured; other cached parcel observations reference original inventory.']}
    (LAB/'cheongju_integrated_ledger_v2_4000.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
