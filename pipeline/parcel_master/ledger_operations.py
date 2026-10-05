"""Local source publication via immutable candidate DBs and a transactional pointer.

This lane never modifies the existing city/4,000-PK databases or product DBs.
"""
import gzip
import json
import os
import re
import sqlite3
from pathlib import Path

from integrated_ledger_v2 import CONTRACT,NAMESPACE,connect,digest,encode,ingest
from ledger_identity_v2 import VERSION
from ledger_release_cli import open_ledger,RESEARCH
from ledger_supply_bundle import sha
from ledger_supply_artifacts import write_gzip_atomic,write_json_atomic
from run_cheongju_integrated_ledger_city import snapshot_deltas

PACKAGE='ledger-normalized-full-snapshot-v1'


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,95}',value):raise ValueError('Invalid batch id')
    return value


def child(root,path):
    value=Path(path)
    if not value.is_absolute():value=Path(root)/value
    value=value.resolve()
    if not value.is_relative_to(Path(root).resolve()):raise ValueError('Path escapes operations lane')
    return value


def unique_object(pairs):
    out={}
    for key,value in pairs:
        if key in out:raise ValueError('Duplicate JSON key: '+key)
        out[key]=value
    return out


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=unique_object)


def extract_release(path,release):
    db=open_ledger(Path(path));before=sha(path)
    try:
        row=db.execute('SELECT manifest FROM release WHERE id=?',(release,)).fetchone()
        if row is None:raise ValueError('Unknown source release')
        manifest=json.loads(row[0])
        buildings={pk:{'raw':json.loads(raw),'attributes':json.loads(attrs)} for pk,raw,attrs in db.execute('''
           SELECT o.pk,r.raw,a.payload FROM building_observation o JOIN building_raw r ON r.pk=o.pk AND r.hash=o.raw_hash
           JOIN building_attribute a ON a.pk=o.pk AND a.hash=o.attribute_hash WHERE o.release_id=?''',(release,))}
        traits={pnu:{'raw':json.loads(raw),'original_dbf':json.loads(original) if original else None}
                for pnu,raw,original in db.execute('SELECT pnu,raw,original_dbf FROM parcel_observation WHERE release_id=?',(release,))}
    finally:db.close()
    if sha(path)!=before:raise ValueError('Export source changed during extraction')
    return manifest,buildings,traits,before


def scope_hash(manifest):
    return digest({**{k:manifest.get(k) for k in ('cohort','scope_sha256','temporal_policy','field_extension')},
                   'districts':sorted(manifest['districts'])})


class Operations:
    def __init__(self,root,allowed_parent=RESEARCH):
        self.root=Path(root).resolve();parent=Path(allowed_parent).resolve()
        if self.root.parent!=parent or not self.root.name.startswith('operations_'):raise ValueError('Separate operations_* research lane required')
        self.root.mkdir(exist_ok=True)
        path=child(self.root,'registry.sqlite')
        self.db=sqlite3.connect(path);self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS publication(id TEXT PRIMARY KEY,db_path TEXT NOT NULL,db_sha TEXT NOT NULL,
            release_id TEXT NOT NULL,snapshot TEXT NOT NULL,scope_sha TEXT NOT NULL,stage_sha TEXT NOT NULL,impact_sha TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY CHECK(id=1),active_id TEXT REFERENCES publication(id),
            latest_id TEXT REFERENCES publication(id),revision INTEGER NOT NULL);
          INSERT OR IGNORE INTO control VALUES(1,NULL,NULL,0);
          CREATE TABLE IF NOT EXISTS event(id INTEGER PRIMARY KEY,action TEXT,previous_id TEXT,next_id TEXT,revision INTEGER);
        ''')

    def close(self):self.db.close()

    def state(self):
        active,latest,revision=self.db.execute('SELECT active_id,latest_id,revision FROM control WHERE id=1').fetchone()
        return {'active_id':active,'latest_id':latest,'revision':revision,'product_enrichment':False,'production_apply':False}

    def active(self):
        state=self.state()
        if state['active_id'] is None:return state,None
        row=self.db.execute('SELECT db_path,db_sha,release_id,snapshot,scope_sha FROM publication WHERE id=?',(state['active_id'],)).fetchone()
        path=child(self.root,row[0])
        if sha(path)!=row[1]:raise ValueError('Published database changed')
        return state,{'path':path,'sha256':row[1],'release':row[2],'snapshot':row[3],'scope_sha':row[4]}

    def export_package(self,source,release,batch_id):
        identifier(batch_id);folder=child(self.root,'inbox/'+batch_id)
        manifest,b,p,source_hash=extract_release(source,release)
        package={'package':PACKAGE,'batch_id':batch_id,'consumer_contract':CONTRACT,'coverage':'full_snapshot',
                 'evidence_kind':'historical_rehearsal','scope_sha256':scope_hash(manifest),'manifest':manifest,
                 'normalization_origin':{'ledger_sha256':source_hash,'release_id':release,
                    'raw_originals_reextracted':False},'payloads':{}}
        if folder.exists():
            old,b2,p2=self.load_package(folder/'package.json')
            if old['normalization_origin']!=package['normalization_origin'] or b!=b2 or p!=p2:raise ValueError('Existing intake differs')
            return folder/'package.json'
        folder.mkdir(parents=True)
        for name,payload in [('buildings',b),('traits',p)]:
            path=folder/(name+'.json.gz');write_gzip_atomic(path,payload)
            package['payloads'][name]={'file':path.name,'sha256':sha(path),'content_sha256':digest(payload),'rows':len(payload)}
        write_json_atomic(folder/'package.json',package)
        return folder/'package.json'

    def load_package(self,path):
        path=child(self.root,path);package=read_json(path)
        identifier(package['batch_id'])
        if package['package']!=PACKAGE or package['coverage']!='full_snapshot' or package['consumer_contract']!=CONTRACT:
            raise ValueError('Only complete normalized source snapshots are accepted')
        m=package['manifest']
        if m['identity_rule']!=VERSION or m['pk_namespace']!=NAMESPACE or package['scope_sha256']!=scope_hash(m):
            raise ValueError('Source rule, namespace or coverage conflict')
        if package['evidence_kind'] not in ('historical_rehearsal','new_source_candidate'):raise ValueError('Explicit evidence kind required')
        if set(package['payloads'])!={'buildings','traits'}:raise ValueError('Incomplete source payload list')
        values=[]
        for name in ('buildings','traits'):
            info=package['payloads'][name];source=child(path.parent,info['file'])
            count=m['expected_'+name]
            if isinstance(count,bool) or not isinstance(count,int) or count<1:raise ValueError('Nonempty complete source counts required')
            if sha(source)!=info['sha256']:raise ValueError('Intake payload hash changed')
            with gzip.open(source,'rt',encoding='utf-8') as f:value=json.load(f,object_pairs_hook=unique_object)
            if not isinstance(value,dict) or digest(value)!=info['content_sha256'] or len(value)!=info['rows'] or len(value)!=m['expected_'+name]:
                raise ValueError('Intake content/count conflict')
            values.append(value)
        return package,*values

    def stage(self,package_path,fail_at=None):
        package_path=child(self.root,package_path);receipt_sha=sha(package_path)
        package,b,p=self.load_package(package_path);batch=package['batch_id'];state,base=self.active()
        folder=child(self.root,'candidates/'+batch)
        if folder.exists():
            stage=self.verify_stage(batch)
            if stage['package_sha256']!=receipt_sha:raise ValueError('Stage receipt changed')
            published=self.db.execute('SELECT stage_sha FROM publication WHERE id=?',(batch,)).fetchone()
            if not published and (stage['expected_revision']!=state['revision'] or stage['expected_base']!=state['active_id']):
                raise ValueError('Staged candidate has an obsolete publication base')
            return stage
        if state['active_id']!=state['latest_id']:raise ValueError('Restore latest publication before staging')
        m=package['manifest']
        if base and (package['scope_sha256']!=base['scope_sha'] or m['title_snapshot']<=base['snapshot']):
            raise ValueError('Coverage must agree and source month must increase')
        folder.mkdir(parents=True)
        path=folder/'ledger.sqlite';db=None
        try:
            if base:
                source=sqlite3.connect(base['path'].as_uri()+'?mode=ro',uri=True)
                try:
                    destination=sqlite3.connect(path);source.backup(destination);destination.close()
                finally:source.close()
            db=connect(path)
            ordinal=db.execute('SELECT COALESCE(MAX(ordinal),0)+1 FROM release').fetchone()[0]
            ingest(db,batch,ordinal,b,p,m,fail_at=fail_at)
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Staged DB integrity failed')
            impact={'batch_id':batch,'previous_id':state['active_id'],'snapshot':m['title_snapshot'],
                    'delta':snapshot_deltas(db)[-1],'identity_statuses':dict(db.execute('SELECT identity_status,count(*) FROM building_observation WHERE release_id=? GROUP BY identity_status',(batch,))),
                    'price_statuses':dict(db.execute('SELECT status,count(*) FROM price_observation WHERE release_id=? GROUP BY status',(batch,))),
                    'last_seen_only_buildings':db.execute('SELECT count(*) FROM current_building WHERE last_seen_release<>?',(batch,)).fetchone()[0],
                    'evidence_kind':package['evidence_kind'],'product_permissions':{'product_enrichment':False,'quantity_aggregation':False,'regression':False},
                    'missing_is_not_demolition':True,'raw_originals_reextracted':False}
            db.close();db=None
            if self.state()!=state or (base and sha(base['path'])!=base['sha256']) or sha(package_path)!=receipt_sha:
                raise ValueError('Publication or intake changed during staging')
            write_json_atomic(folder/'impact.json',impact)
            stage={'batch_id':batch,'expected_base':state['active_id'],'expected_revision':state['revision'],
                   'database':'ledger.sqlite','database_sha256':sha(path),'impact_sha256':sha(folder/'impact.json'),
                   'package_path':str(package_path.relative_to(self.root)),'package_sha256':receipt_sha,
                   'snapshot':m['title_snapshot'],'scope_sha256':package['scope_sha256'],'evidence_kind':package['evidence_kind'],
                   'consumer_contract':CONTRACT,'production_apply':False}
            write_json_atomic(folder/'stage.json',stage)
            return stage
        except BaseException:
            if db is not None:db.close()
            # Remove only this failed attempt's named artifacts, never a published version.
            for name in ('ledger.sqlite','ledger.sqlite-journal','impact.json','stage.json'):
                child(folder,name).unlink(missing_ok=True)
            folder.rmdir()
            raise

    def verify_stage(self,batch):
        identifier(batch);folder=child(self.root,'candidates/'+batch);stage=read_json(folder/'stage.json')
        if stage['batch_id']!=batch or stage['consumer_contract']!=CONTRACT or stage['production_apply'] is not False:raise ValueError('Stage contract conflict')
        if stage['database']!='ledger.sqlite' or sha(folder/'ledger.sqlite')!=stage['database_sha256'] or sha(folder/'impact.json')!=stage['impact_sha256']:
            raise ValueError('Staged database/impact changed')
        if sha(child(self.root,stage['package_path']))!=stage['package_sha256']:raise ValueError('Stage package changed')
        receipt_path=child(self.root,stage['package_path']);receipt=read_json(receipt_path)
        for info in receipt['payloads'].values():
            if sha(child(receipt_path.parent,info['file']))!=info['sha256']:raise ValueError('Staged input payload changed')
        impact=read_json(folder/'impact.json')
        if impact['product_permissions']!={'product_enrichment':False,'quantity_aggregation':False,'regression':False}:
            raise ValueError('Source publication cannot promote product permissions')
        return stage

    def publish(self,batch,impact_sha,expected_revision,fail_at=None):
        stage=self.verify_stage(batch)
        if impact_sha!=stage['impact_sha256']:raise ValueError('Reviewed impact hash required')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            state=self.state()
            existing=self.db.execute('SELECT stage_sha FROM publication WHERE id=?',(batch,)).fetchone()
            stage_path=child(self.root,'candidates/'+batch+'/stage.json');stage_sha=sha(stage_path)
            if existing:
                if existing[0]!=stage_sha or state['active_id']!=batch:raise ValueError('Published batch replay conflict')
                self.db.rollback();return False
            if state['revision']!=expected_revision or stage['expected_revision']!=expected_revision or state['active_id']!=stage['expected_base'] or state['active_id']!=state['latest_id']:
                raise ValueError('Stale publication base/revision')
            self.active()
            self.db.execute('INSERT INTO publication VALUES(?,?,?,?,?,?,?,?)',(batch,'candidates/'+batch+'/ledger.sqlite',stage['database_sha256'],
                            batch,stage['snapshot'],stage['scope_sha256'],stage_sha,impact_sha))
            self.db.execute('UPDATE control SET active_id=?,latest_id=?,revision=revision+1 WHERE id=1',(batch,batch))
            if fail_at=='pointer':raise RuntimeError('Injected pointer publication failure')
            self.db.execute('INSERT INTO event(action,previous_id,next_id,revision) VALUES(?,?,?,?)',('publish',state['active_id'],batch,state['revision']+1))
            self.db.commit();return True
        except BaseException:self.db.rollback();raise

    def restore(self,batch,expected_revision,fail_at=None):
        identifier(batch);self.db.execute('BEGIN IMMEDIATE')
        try:
            state=self.state()
            if state['revision']!=expected_revision:raise ValueError('Stale restore revision')
            row=self.db.execute('SELECT db_path,db_sha FROM publication WHERE id=?',(batch,)).fetchone()
            if row is None or sha(child(self.root,row[0]))!=row[1]:raise ValueError('Unknown or changed restore target')
            if state['active_id']==batch:self.db.rollback();return False
            self.db.execute('UPDATE control SET active_id=?,revision=revision+1 WHERE id=1',(batch,))
            if fail_at=='pointer':raise RuntimeError('Injected pointer restore failure')
            self.db.execute('INSERT INTO event(action,previous_id,next_id,revision) VALUES(?,?,?,?)',('restore',state['active_id'],batch,state['revision']+1))
            self.db.commit();return True
        except BaseException:self.db.rollback();raise
