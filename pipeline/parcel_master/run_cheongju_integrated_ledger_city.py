"""Apply the same integrated schema/rule/contract to the full frozen Cheongju scope."""
import csv
import gzip
import json
import sys
from collections import Counter
from time import perf_counter

from audit_cheongju_relation_source_evidence import scan_titles, title_path
from integrated_ledger_v2 import CONTRACT, NAMESPACE, connect, fingerprint, ingest, restore
from ledger_identity_v2 import VERSION, identify
from run_cheongju_integrated_ledger_v2 import OUT, LAB, file_hash


def snapshot_deltas(db):
    result=[];previous=None
    for release,snapshot in db.execute('SELECT id,json_extract(manifest,\'$.title_snapshot\') FROM release ORDER BY ordinal').fetchall():
        item={'snapshot':snapshot,'previous_release':previous}
        for table,key,fields in [('building_observation','pk',['raw_hash','attribute_hash']),
                                 ('parcel_observation','pnu',['version_hash'])]:
            current=db.execute('SELECT count(*) FROM '+table+' WHERE release_id=?',(release,)).fetchone()[0]
            if previous is None:
                item[table]={'observations':current,'new_vs_previous_snapshot':current,'missing_vs_previous_snapshot':0,
                             **{field+'_changed':0 for field in fields}}
                continue
            join=' FROM '+table+' n JOIN '+table+' p ON n.'+key+'=p.'+key+' WHERE n.release_id=? AND p.release_id=?'
            shared=db.execute('SELECT count(*)'+join,(release,previous)).fetchone()[0]
            prior=db.execute('SELECT count(*) FROM '+table+' WHERE release_id=?',(previous,)).fetchone()[0]
            item[table]={'observations':current,'new_vs_previous_snapshot':current-shared,'missing_vs_previous_snapshot':prior-shared,
                         **{field+'_changed':db.execute('SELECT count(*)'+join+' AND n.'+field+'<>p.'+field,(release,previous)).fetchone()[0] for field in fields}}
        item['price_changed_among_shared_parcels']=db.execute('''SELECT count(*) FROM price_observation n JOIN price_observation p ON n.pnu=p.pnu
          WHERE n.release_id=? AND p.release_id=? AND (n.raw_price<>p.raw_price OR n.raw_year<>p.raw_year OR n.status<>p.status)''',(release,previous)).fetchone()[0] if previous else 0
        for field in ('raw_price','raw_year'):
            item[field+'_changed_among_shared_parcels']=db.execute('SELECT count(*) FROM price_observation n JOIN price_observation p ON n.pnu=p.pnu WHERE n.release_id=? AND p.release_id=? AND n.'+field+'<>p.'+field,(release,previous)).fetchone()[0] if previous else 0
        result.append(item);previous=release
    return result


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    started=perf_counter();coverage=json.loads((LAB/'cheongju_building_trait_coverage.json').read_text(encoding='utf-8'))
    inventory=json.loads((LAB/'cheongju_relation_source_evidence.json').read_text(encoding='utf-8'))['raw_inventory']
    db_path=OUT/'integrated_ledger_v2_cheongju.sqlite';db=connect(db_path)
    batches=[];checks={};releases=[];input_hashes={};last_inputs=None
    for ordinal,pair in enumerate(coverage['pairs'],1):
        snapshot=pair['building_snapshot'];tick=perf_counter()
        processed_path=OUT/f'building_identity_{snapshot}.csv.gz';trait_path=OUT/f'traits_{snapshot[:4]}.csv.gz'
        for kind,path in [('buildings',processed_path),('traits',trait_path)]:
            sha=file_hash(path)
            if sha!=pair['input_sha256'][kind]:raise ValueError('Frozen city input changed')
            input_hashes[path.name]=sha
        with gzip.open(processed_path,'rt',encoding='utf-8',newline='') as f:
            attrs={}
            for row in csv.DictReader(f):
                pk=row['mgmt_pk']
                if pk in attrs or row['snapshot']!=snapshot:raise ValueError('City processed key/snapshot conflict')
                attrs[pk]=row
        if len(attrs)!=pair['metrics']['building_rows']:raise ValueError('City scope row count conflict')
        found,meta=scan_titles(title_path(snapshot),set(attrs))
        expected=next(r for r in inventory if r['source']=='title' and r['snapshot']==snapshot)
        if meta['sha256']!=expected['sha256'] or meta['rows']!=expected['rows'] or meta['duplicate_target_pks']:
            raise ValueError('City source integrity conflict')
        if set(found)!=set(attrs):raise ValueError('City original building scope incomplete')
        buildings={pk:{'raw':rows[0],'attributes':attrs[pk]} for pk,rows in found.items()}
        del found,attrs
        traits={}
        with gzip.open(trait_path,'rt',encoding='utf-8',newline='') as f:
            for row in csv.DictReader(f):
                pnu=row['pnu']
                if pnu in traits:raise ValueError('Duplicate city parcel')
                traits[pnu]={'raw':row,'original_dbf':None}
        if {p[:5] for p in traits}!={'43111','43112','43113','43114'}:raise ValueError('Incomplete city district scope')
        source={'title':{'sha256':meta['sha256'],'file':meta['filename'],'source_snapshot':snapshot,'base_date':None,'collected_at':None,
                         'preservation':'original_selected_fields_replayed_entire_file'},
                'traits':{'sha256':input_hashes[trait_path.name],'base_date':pair['trait_cutoff'],'collected_at':None,
                          'source_year':pair['trait_year'],'raw_dbf_zip_inventory':[r for r in inventory if r['source']=='traits' and r['year']==pair['trait_year']]},
                'processed_building':{'sha256':input_hashes[processed_path.name],'base_date':None,'collected_at':None,
                                      'attribute_origin':'frozen_processed_extract_crosschecked_raw_area_fields'}}
        manifest={'identity_rule':VERSION,'pk_namespace':NAMESPACE,'title_snapshot':snapshot,'trait_year':pair['trait_year'],
                  'districts':['43111','43112','43113','43114'],'expected_buildings':len(buildings),'expected_traits':len(traits),
                  'sources':source,'cohort':'full_frozen_cheongju_building_scope_and_all_city_trait_candidates',
                  'temporal_policy':'same_year_research_only'}
        release=f'cheongju-city-{snapshot}-identity-2.2';releases.append(release)
        t=perf_counter();inserted=ingest(db,release,ordinal,buildings,traits,manifest);ingest_seconds=perf_counter()-t
        # Content/manifest replay is checked without collecting whole database rows.
        checks[snapshot+'_idempotent']=ingest(db,release,ordinal,buildings,traits,manifest) is False
        batches.append({'snapshot':snapshot,'building_observations':len(buildings),'all_city_trait_candidates':len(traits),
                        'identity_statuses':dict(Counter(identify(r['raw']['raw_identity_fields'])['status'] for r in buildings.values())),
                        'new_release_inserted':inserted,'ingest_seconds':ingest_seconds,'source_prepare_and_replay_seconds':perf_counter()-tick})
        print('city published',snapshot,len(buildings),len(traits),round(ingest_seconds,2),flush=True)
        last_inputs=(buildings,traits,manifest)
    baseline=fingerprint(db);t=perf_counter();restore(db,releases[0]);restore(db,releases[-1])
    restore_seconds=perf_counter()-t;checks['oldest_and_latest_restore_exact']=fingerprint(db)==baseline
    b,p,m=last_inputs
    # Subset failure tests publication on the full-size history/current indexes;
    # this measures rollback safety, not a real partial city update.
    small_b=dict(list(b.items())[:20]);small_p=dict(list(p.items())[:20]);small_m={**m,'expected_buildings':20,'expected_traits':20,'cohort':'injected_failure_subset_only'}
    t=perf_counter()
    try:ingest(db,'injected-city-failure',4,small_b,small_p,small_m,fail_at='published')
    except RuntimeError:pass
    checks['failure_after_full_size_current_publication']=fingerprint(db)==baseline;rollback_seconds=perf_counter()-t
    checks['foreign_keys_clean']=not db.execute('PRAGMA foreign_key_check').fetchall()
    checks['integrity']=db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    checks['no_zero_main_canonical_relation']=db.execute("SELECT count(*) FROM address_relation WHERE substr(pnu,12,4)='0000'").fetchone()[0]==0
    tables={r[0]:db.execute('SELECT count(*) FROM '+r[0]).fetchone()[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    latest=releases[-1]
    observed=db.execute('SELECT count(*) FROM building_observation WHERE release_id=?',(latest,)).fetchone()[0]
    stale=tables['current_building']-observed
    report={'rule_version':VERSION,'consumer_contract':CONTRACT,'batches':batches,'tables':tables,'snapshot_deltas':snapshot_deltas(db),
            'current_buildings':tables['current_building'],'latest_observed_buildings':observed,'last_seen_only_buildings':stale,
            'restore_oldest_then_latest_seconds':restore_seconds,'injected_subset_rollback_seconds':rollback_seconds,
            'checks':checks,'frozen_inputs_sha256':input_hashes,'sqlite_bytes':db_path.stat().st_size,'elapsed_seconds':perf_counter()-started,
            'limitations':['Three frozen city building snapshots; not legal nationwide completeness.',
                           'Traits retain all city candidate parcels; original DBF columns are referenced by inventory, not re-copied in this city run.',
                           'Same schema and identity/consumer contract as the 4,000 PK stage; no production assignments or regression adoption.',
                           'No real future source delta available; idempotency and injected subset rollback are not a certified new-month incremental update.']}
    db.close()
    checks['frozen_input_hashes_unchanged']=input_hashes=={name:file_hash(OUT/name) for name in input_hashes}
    if not all(checks.values()):raise AssertionError(checks)
    (LAB/'cheongju_integrated_ledger_v2_city.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
