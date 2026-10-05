"""Fixed local inputs -> stratified normalized SQLite prototype and aggregate QA."""
import hashlib
import json
from datetime import date
from pathlib import Path

import pandas as pd

from building_relation_staging import connect, ingest, restore, state_fingerprint, DISTRICTS

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/research/cheongju_ledger'
LAB=ROOT/'docs/lab'


def main():
    coverage=json.loads((LAB/'cheongju_building_trait_coverage.json').read_text(encoding='utf-8'))
    frames={}
    for pair in coverage['pairs']:
        path=OUT/f"building_identity_{pair['building_snapshot']}.csv.gz"
        if hashlib.sha256(path.read_bytes()).hexdigest()!=pair['input_sha256']['buildings']:
            raise ValueError('Frozen building input changed')
        frame=pd.read_csv(path,dtype=str,keep_default_na=False)
        if len(frame)!=pair['metrics']['building_rows'] or not frame.mgmt_pk.is_unique:
            raise ValueError('Building count/key conflict')
        frames[pair['building_snapshot']]=frame
    ordered=sorted(frames)
    forced=set()
    for a,b in zip(ordered,ordered[1:]):
        old=frames[a].set_index('mgmt_pk').pnu; new=frames[b].set_index('mgmt_pk').pnu
        common=old.index.intersection(new.index)
        forced.update(common[old.loc[common].ne(new.loc[common])])
    identities=pd.concat(list(frames.values()),ignore_index=True).drop_duplicates('mgmt_pk').set_index('mgmt_pk')
    scope=set()
    for district in sorted(DISTRICTS):
        candidates=set(identities.index[identities.pnu.str[:5].eq(district)])
        required=candidates&forced
        if len(required)>1000: raise ValueError('Forced examples exceed stratum scope')
        ranked=sorted(candidates-required,key=lambda pk:hashlib.sha256(pk.encode()).hexdigest())
        scope.update(required|set(ranked[:1000-len(required)]))
    if len(scope)!=4000 or not forced<=scope: raise ValueError('Incomplete deterministic scope')
    scope_sha=hashlib.sha256('\n'.join(sorted(scope)).encode()).hexdigest()
    selected={snapshot:frame[frame.mgmt_pk.isin(scope)].copy() for snapshot,frame in frames.items()}
    all_pnus=set().union(*(set(frame.pnu) for frame in selected.values()))
    db_path=OUT/'building_relation_staging.sqlite'
    db=connect(db_path)
    report={'run_date':date.today().isoformat(),'version':'building-relation-staging-v1',
            'scope_management_pks':len(scope),'scope_sha256':scope_sha,
            'address_change_management_pks_included':len(forced), 'scope_parcels':len(all_pnus),
            'sampling':'1000 management PKs per earliest observed district; all adjacent-snapshot PNU-change PKs forced in; remaining PKs selected by SHA256 order.',
            'snapshots':[], 'checks':{},
            'limitations':['Sample deliberately includes address-change cases; sample change rates are not city estimates.',
                           'Address relations are observed representative title addresses, not certified complete sites or transaction targets.',
                           'Missing observations are retained stale, not classified as demolition or deletion.',
                           'SQLite is an isolated local experiment, not a production schema or migration.',
                           'Building attributes come from the existing processed DB extract, not untouched source text.',
                           'Trait observations use same-year sources with different observation dates.']}
    last_inputs=None
    for pair in coverage['pairs']:
        year=pair['trait_year']; snapshot=pair['building_snapshot']; path=OUT/f'traits_{year}.csv.gz'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=pair['input_sha256']['traits']:
            raise ValueError('Trait source changed')
        pieces=[]
        for chunk in pd.read_csv(path,dtype=str,keep_default_na=False,chunksize=100000):
            pieces.append(chunk[chunk.pnu.isin(all_pnus)])
        traits=pd.concat(pieces,ignore_index=True).to_dict('records')
        buildings=selected[snapshot].to_dict('records')
        manifest={'source_districts':sorted(DISTRICTS),'scope_sha256':scope_sha,
                  'building_sha256':pair['input_sha256']['buildings'],'trait_sha256':pair['input_sha256']['traits'],
                  'expected_buildings':len(buildings),'expected_traits':len(traits),'trait_year':year,
                  'trait_cutoff':pair['trait_cutoff'],'collected_at':coverage['run_date']}
        counts=ingest(db,snapshot,buildings,traits,manifest)
        before=state_fingerprint(db)
        replay=ingest(db,snapshot,buildings,traits,manifest)
        if not replay['idempotent_replay'] or state_fingerprint(db)!=before:
            raise AssertionError('Replay changed state')
        report['snapshots'].append({'snapshot':snapshot,**{k:v for k,v in counts.items() if k!='idempotent_replay'}})
        last_inputs=(buildings,traits,manifest)
        print(snapshot,json.dumps(counts),flush=True)
    latest=ordered[-1]; before=state_fingerprint(db)
    buildings,traits,manifest=last_inputs
    failure_rows=[{**row,'snapshot':'2027-07','gross_area':'123456.7'} for row in buildings]
    try:
        ingest(db,'2027-07',failure_rows,traits,manifest,fail_after=20)
    except RuntimeError:
        report['checks']['injected_failure_preserved_every_table']=state_fingerprint(db)==before
    else: raise AssertionError('Failure injection did not execute')
    restore(db,ordered[0])
    report['checks']['restored_oldest_head']=db.execute("SELECT value FROM state WHERE key='head'").fetchone()[0]==ordered[0]
    restore(db,latest)
    report['checks']['restored_latest_exact_state']=state_fingerprint(db)==before
    report['checks']['foreign_keys_clean']=not db.execute('PRAGMA foreign_key_check').fetchall()
    report['checks']['one_relation_per_building_observation']=db.execute('SELECT count(*) FROM address_relation_observation').fetchone()[0]==db.execute('SELECT count(*) FROM building_observation').fetchone()[0]
    report['checks']['versions_owned_by_observed_entity']=not db.execute('SELECT 1 FROM building_observation o JOIN building_version v ON v.id=o.version WHERE o.pk<>v.pk LIMIT 1').fetchone() and not db.execute('SELECT 1 FROM parcel_observation o JOIN parcel_version v ON v.id=o.version WHERE o.pnu<>v.pnu LIMIT 1').fetchone()
    report['checks']['all_forced_address_changes_in_scope']=forced<=scope
    report['checks']['idempotent_replay_each_snapshot']=True
    report['checks']['one_price_observation_per_trait_observation']=db.execute('SELECT count(*) FROM assessed_price_observation').fetchone()[0]==db.execute('SELECT count(*) FROM parcel_observation').fetchone()[0]
    report['tables']={table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('source_snapshot','building_entity','parcel_identity','building_version','parcel_version','building_observation','parcel_observation','assessed_price_observation','address_relation_observation','current_building')}
    report['price_observation_statuses']=[{'snapshot':s,'status':status,'rows':n} for s,status,n in db.execute('SELECT snapshot,status,count(*) FROM assessed_price_observation GROUP BY snapshot,status ORDER BY snapshot,status')]
    report['price_observations_with_unknown_year']=db.execute('SELECT count(*) FROM assessed_price_observation WHERE price_year IS NULL').fetchone()[0]
    report['stale_current_buildings']=db.execute('SELECT count(*) FROM current_building WHERE last_snapshot<>?',(latest,)).fetchone()[0]
    review=[]
    for old_snapshot,new_snapshot in zip(ordered,ordered[1:]):
        for pk,old_pnu,new_pnu in db.execute('''SELECT n.pk,o.pnu,n.pnu FROM address_relation_observation n
          JOIN address_relation_observation o ON o.pk=n.pk WHERE o.snapshot=? AND n.snapshot=? AND o.pnu<>n.pnu''',(old_snapshot,new_snapshot)):
            review.append({'reason':'address_pnu_changed','mgmt_pk':pk,'pnu':new_pnu,'previous_pnu':old_pnu,'snapshot':new_snapshot})
    for pk,pnu in db.execute('SELECT pk,pnu FROM address_relation_observation WHERE snapshot=? AND trait_present=0',(latest,)):
        review.append({'reason':'address_without_same_year_trait','mgmt_pk':pk,'pnu':pnu,'previous_pnu':'','snapshot':latest})
    for pk,pnu,last_seen in db.execute('SELECT pk,pnu,last_snapshot FROM current_building WHERE last_snapshot<>?',(latest,)):
        review.append({'reason':'missing_title_observation_retained','mgmt_pk':pk,'pnu':pnu,'previous_pnu':'','snapshot':last_seen})
    for snapshot,pnu,status in db.execute("SELECT snapshot,pnu,status FROM assessed_price_observation WHERE status<>'positive'"):
        review.append({'reason':'price_'+status,'mgmt_pk':'','pnu':pnu,'previous_pnu':'','snapshot':snapshot})
    queue=pd.DataFrame(review)
    queue['sigungu']=queue.pnu.str[:5]
    queue['sample_order']=queue.apply(lambda row:hashlib.sha256((row.reason+row.snapshot+row.pnu+row.mgmt_pk).encode()).hexdigest(),axis=1)
    queue=queue.sort_values('sample_order').groupby(['sigungu','reason'],group_keys=False).head(10).drop(columns=['sample_order'])
    queue['independent_verification']='unverified'; queue['independent_evidence']=''
    queue.to_csv(OUT/'building_relation_review_queue.csv',index=False,encoding='utf-8-sig')
    report['review_queue']={'rows':len(queue),'sampling':'At most 10 observations per district/reason; SHA256 order; independent evidence empty.',
                            'by_reason':{str(k):int(v) for k,v in queue.reason.value_counts().items()}}
    if not all(report['checks'].values()): raise AssertionError('Prototype checks failed')
    db.close(); report['sqlite_bytes']=db_path.stat().st_size
    (LAB/'cheongju_building_relation_staging.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'checks':report['checks'],'tables':report['tables'],'stale_current_buildings':report['stale_current_buildings']}),flush=True)


if __name__=='__main__': main()
